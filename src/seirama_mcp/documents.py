import hashlib
import re
from .config import settings
from .codegraph import edge, node, connection

def category(path):
    try: return path.relative_to(settings.docs_root).parts[0]
    except (ValueError, IndexError): return "Lainnya"

def chunks(text):
    text = re.sub(r"\s+", " ", text).strip()
    if not text: return []
    if settings.document_chunk_size <= 0 or not 0 <= settings.document_chunk_overlap < settings.document_chunk_size: raise ValueError("document_chunk_overlap tidak valid")
    result=[]; start=0
    while start < len(text):
        end=min(start+settings.document_chunk_size,len(text)); result.append(text[start:end])
        if end == len(text): break
        start=end-settings.document_chunk_overlap
    return result

def parse_pdf(path):
    if settings.document_parser == "pypdf":
        from pypdf import PdfReader
        return [(n, p.extract_text() or "") for n,p in enumerate(PdfReader(str(path)).pages,1)]
    try:
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
    except ImportError as error: raise RuntimeError("Parser Docling belum terpasang; gunakan DOCUMENT_PARSER=pypdf") from error
    options=PdfPipelineOptions(); options.do_ocr=settings.document_ocr
    document=DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}).convert(str(path)).document
    page_text={}
    for item,_ in document.iterate_items():
        text=getattr(item,"text","").strip()
        for provenance in getattr(item,"prov",[]) or []:
            number=getattr(provenance,"page_no",None)
            if number is not None and text: page_text.setdefault(number,[]).append(text)
    return [(n,"\n\n".join(parts)) for n,parts in sorted(page_text.items())] or [(1,document.export_to_markdown())]

def qdrant():
    from fastembed import TextEmbedding
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams
    client=QdrantClient(url=settings.qdrant_url); embedder=TextEmbedding(model_name=settings.embedding_model); size=len(list(embedder.embed(["dimension probe"]))[0])
    if not client.collection_exists(settings.qdrant_collection): client.create_collection(collection_name=settings.qdrant_collection,vectors_config=VectorParams(size=size,distance=Distance.COSINE))
    return client,embedder

def index(force=False):
    pdfs=sorted(settings.docs_root.rglob("*.pdf")) if settings.docs_root.exists() else []
    if not pdfs: return {"indexed":0,"skipped":0,"pdf_count":0}
    client,embedder=qdrant(); indexed=skipped=0
    from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct
    for path in pdfs:
        relative=str(path.relative_to(settings.docs_root.parent)).replace("\\", "/"); checksum=hashlib.sha256(path.read_bytes()).hexdigest()
        path_filter=Filter(must=[FieldCondition(key="path", match=MatchValue(value=relative))])
        existing=client.scroll(settings.qdrant_collection, scroll_filter=path_filter, limit=1, with_payload=True)[0]
        if existing and existing[0].payload.get("checksum")==checksum and not force: skipped+=1; continue
        client.delete(collection_name=settings.qdrant_collection, points_selector=path_filter)
        pending=[]; pages=parse_pdf(path)
        for number,page_text in pages:
            text=re.sub(r"(?<!\n)-\n(?=\w)","",page_text or ""); text=re.sub(r"[ \t]+"," ",text).strip()
            for chunk_index,text_chunk in enumerate(chunks(text)):
                point_id=int(hashlib.sha256(f"{relative}:{number}:{chunk_index}".encode()).hexdigest()[:15],16); pending.append((point_id,text_chunk,number,chunk_index))
        if pending:
            vectors=list(embedder.embed([x[1] for x in pending])); client.upsert(collection_name=settings.qdrant_collection,points=[PointStruct(id=i,vector=v.tolist(),payload={"text":t,"path":relative,"filename":path.name,"category":category(path),"page_number":n,"chunk_index":ci,"checksum":checksum,"page_count":len(pages),"indexed":True}) for (i,t,n,ci),v in zip(pending,vectors)])
        indexed+=1
    return {"indexed":indexed,"skipped":skipped,"pdf_count":len(pdfs),"storage":"qdrant"}

def search(query,category_filter,limit):
    client,embedder=qdrant(); vector=list(embedder.embed([query]))[0].tolist(); query_filter=None
    if category_filter:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        query_filter=Filter(must=[FieldCondition(key="category",match=MatchValue(value=category_filter))])
    points=client.query_points(collection_name=settings.qdrant_collection,query=vector,query_filter=query_filter,limit=limit,with_payload=True).points
    return [{"score":p.score,**(p.payload or {})} for p in points]

def get(path,page_number=None):
    normalized=path.replace("\\", "/").lstrip("./")
    client,_=qdrant(); from qdrant_client.models import FieldCondition, Filter, MatchValue
    conditions=[FieldCondition(key="path",match=MatchValue(value=normalized))]
    if page_number is not None: conditions.append(FieldCondition(key="page_number",match=MatchValue(value=page_number)))
    points=client.scroll(settings.qdrant_collection,scroll_filter=Filter(must=conditions),limit=10000,with_payload=True)[0]
    if not points:
        requested_name=normalized.rsplit("/",1)[-1].casefold()
        candidates=client.scroll(settings.qdrant_collection,limit=10000,with_payload=True)[0]
        points=[point for point in candidates if (point.payload or {}).get("filename","").casefold()==requested_name or (point.payload or {}).get("path","").casefold()==normalized.casefold()]
        if page_number is not None: points=[point for point in points if (point.payload or {}).get("page_number")==page_number]
    if not points: return {"found":False,"path":path,"pages":[],"storage":"qdrant"}
    payloads=[p.payload or {} for p in points]; first=payloads[0]
    pages={}
    for item in sorted(payloads,key=lambda value:(value.get("page_number",0),value.get("chunk_index",0))):
        number=item.get("page_number"); pages[number]=(pages.get(number,"") + "\n\n" + item.get("text","")).strip()
    return {"found":True,"storage":"qdrant","document":{key:first.get(key) for key in ("path","filename","category","page_count","checksum")},"pages":[{"page_number":number,"text":text} for number,text in sorted(pages.items())]}

def list_documents(category_filter=None):
    client,_=qdrant(); from qdrant_client.models import FieldCondition, Filter, MatchValue
    scroll_filter=Filter(must=[FieldCondition(key="category",match=MatchValue(value=category_filter))]) if category_filter else None
    points=client.scroll(settings.qdrant_collection,scroll_filter=scroll_filter,limit=10000,with_payload=True)[0]
    unique={item.get("path"):item for item in (p.payload or {} for p in points) if item.get("path")}
    return {"count":len(unique),"storage":"qdrant","documents":[{key:item.get(key) for key in ("path","filename","category","page_count","checksum","indexed")} for item in sorted(unique.values(),key=lambda x:(x.get("category",""),x.get("filename","")))]}

def categories():
    documents=list_documents()["documents"]; counts={}
    for item in documents: counts[item["category"]]=counts.get(item["category"],0)+1
    return {"count":len(counts),"storage":"qdrant","categories":[{"category":key,"count":value} for key,value in sorted(counts.items())]}

def text_search(query, category_filter=None, limit=30):
    client,_=qdrant(); from qdrant_client.models import FieldCondition, Filter, MatchValue
    scroll_filter=Filter(must=[FieldCondition(key="category",match=MatchValue(value=category_filter))]) if category_filter else None
    points=client.scroll(settings.qdrant_collection,scroll_filter=scroll_filter,limit=10000,with_payload=True)[0]
    terms=[term for term in re.findall(r"[\w-]+",query.lower()) if len(term)>2]
    return [{**(p.payload or {}),"storage":"qdrant"} for p in points if any(term in (p.payload or {}).get("text","").lower() for term in terms)][:limit]
