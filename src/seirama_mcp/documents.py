import hashlib
import re
from .config import settings
from .codegraph import edge, node, connection

def setup(db):
    db.executescript("CREATE TABLE IF NOT EXISTS documents (id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, category TEXT NOT NULL, filename TEXT NOT NULL, checksum TEXT NOT NULL, page_count INTEGER NOT NULL DEFAULT 0, indexed INTEGER NOT NULL DEFAULT 0); CREATE TABLE IF NOT EXISTS document_pages (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL, page_number INTEGER NOT NULL, text TEXT NOT NULL, UNIQUE(document_id, page_number)); CREATE TABLE IF NOT EXISTS document_chunks (id INTEGER PRIMARY KEY, document_id INTEGER NOT NULL, page_number INTEGER NOT NULL, chunk_index INTEGER NOT NULL, text TEXT NOT NULL, UNIQUE(document_id, page_number, chunk_index));")

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
    db=connection(); setup(db); pdfs=sorted(settings.docs_root.rglob("*.pdf")) if settings.docs_root.exists() else []
    if not pdfs: db.close(); return {"indexed":0,"skipped":0,"pdf_count":0}
    client,embedder=qdrant(); indexed=skipped=0
    from qdrant_client.models import FieldCondition, Filter, MatchValue, PointStruct
    for path in pdfs:
        relative=str(path.relative_to(settings.docs_root.parent)); checksum=hashlib.sha256(path.read_bytes()).hexdigest(); old=db.execute("SELECT id,checksum,indexed FROM documents WHERE path=?",(relative,)).fetchone()
        if old and old[1]==checksum and old[2] and not force: skipped+=1; continue
        if old: document_id=old[0]; db.execute("DELETE FROM document_pages WHERE document_id=?",(document_id,)); db.execute("DELETE FROM document_chunks WHERE document_id=?",(document_id,)); db.execute("UPDATE documents SET checksum=?,indexed=0 WHERE id=?",(checksum,document_id))
        else: document_id=db.execute("INSERT INTO documents(path,category,filename,checksum) VALUES(?,?,?,?)",(relative,category(path),path.name,checksum)).lastrowid
        pending=[]; pages=parse_pdf(path)
        for number,page_text in pages:
            text=re.sub(r"(?<!\n)-\n(?=\w)","",page_text or ""); text=re.sub(r"[ \t]+"," ",text).strip(); db.execute("INSERT INTO document_pages(document_id,page_number,text) VALUES(?,?,?)",(document_id,number,text))
            for chunk_index,text_chunk in enumerate(chunks(text)):
                chunk_id=db.execute("INSERT INTO document_chunks(document_id,page_number,chunk_index,text) VALUES(?,?,?,?)",(document_id,number,chunk_index,text_chunk)).lastrowid; pending.append((int(chunk_id),text_chunk,number))
        if pending:
            vectors=list(embedder.embed([x[1] for x in pending])); client.upsert(collection_name=settings.qdrant_collection,points=[PointStruct(id=i,vector=v.tolist(),payload={"text":t,"path":relative,"category":category(path),"page_number":n,"chunk_id":i}) for (i,t,n),v in zip(pending,vectors)])
        db.execute("UPDATE documents SET page_count=?,indexed=1 WHERE id=?",(len(pages),document_id)); edge(db,node(db,"document",path.name,relative),"HAS_CATEGORY",node(db,"document_category",category(path))); db.commit(); indexed+=1
    db.close(); return {"indexed":indexed,"skipped":skipped,"pdf_count":len(pdfs)}

def search(query,category_filter,limit):
    client,embedder=qdrant(); vector=list(embedder.embed([query]))[0].tolist(); query_filter=None
    if category_filter:
        from qdrant_client.models import FieldCondition, Filter, MatchValue
        query_filter=Filter(must=[FieldCondition(key="category",match=MatchValue(value=category_filter))])
    points=client.query_points(collection_name=settings.qdrant_collection,query=vector,query_filter=query_filter,limit=limit,with_payload=True).points
    return [{"score":p.score,**(p.payload or {})} for p in points]

def get(path,page_number=None):
    db=connection(); setup(db); doc=db.execute("SELECT id,path,category,filename,page_count FROM documents WHERE path=?",(path,)).fetchone()
    if doc is None: db.close(); return {"found":False,"path":path,"pages":[]}
    sql="SELECT page_number,text FROM document_pages WHERE document_id=?"; params=[doc[0]]
    if page_number is not None: sql+=" AND page_number=?"; params.append(page_number)
    pages=db.execute(sql+" ORDER BY page_number",params).fetchall(); db.close(); return {"found":True,"document":dict(doc),"pages":[dict(p) for p in pages]}
