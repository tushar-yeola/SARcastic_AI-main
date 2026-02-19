"""
ChromaDB Vector Store for Regulatory Knowledge Base

In Docker mode (CHROMA_SERVER_HOST set), uses an in-memory regulatory store
to avoid the 79MB ONNX model download that blocks startup.

In local mode, uses ChromaDB PersistentClient for full vector search.
"""

import os


class InMemoryRegStore:
    """
    Fast, in-memory regulatory document store that uses simple keyword matching.
    Pre-loaded with key BSA/AML regulatory guidance for SAR generation.
    """
    def __init__(self):
        self.docs = []
        
    def add(self, documents, ids, metadatas=None):
        for i, doc in enumerate(documents):
            self.docs.append({
                "id": ids[i],
                "text": doc,
                "metadata": metadatas[i] if metadatas else {}
            })
            
    def query(self, query_texts, n_results=2):
        results = []
        for q in query_texts:
            q_lower = q.lower()
            # Score docs by keyword overlap
            scored = []
            for doc in self.docs:
                score = sum(1 for word in q_lower.split() if word in doc["text"].lower())
                scored.append((score, doc["text"]))
            scored.sort(reverse=True, key=lambda x: x[0])
            matches = [s[1] for s in scored[:n_results]]
            if not matches and self.docs:
                matches = [d["text"] for d in self.docs[:n_results]]
            results.append(matches)
        return {"documents": results}
        
    def count(self):
        return len(self.docs)


# Determine mode
CHROMA_HOST = os.getenv("CHROMA_SERVER_HOST")

if CHROMA_HOST:
    # Docker mode: use in-memory store (avoids ONNX download)
    print("Using in-memory regulatory store (Docker mode)")
    collection = InMemoryRegStore()
else:
    # Local mode: try ChromaDB
    try:
        import chromadb
        from chromadb.utils import embedding_functions
        
        PERSIST_DIRECTORY = os.path.join(os.getcwd(), "chroma_db")
        client = chromadb.PersistentClient(path=PERSIST_DIRECTORY)
        embedding_function = embedding_functions.DefaultEmbeddingFunction()
        collection = client.get_or_create_collection(
            name="sar_regulations",
            embedding_function=embedding_function
        )
        print("Using ChromaDB PersistentClient (local mode)")
    except Exception as e:
        print(f"Warning: Failed to initialize ChromaDB: {e}. Using in-memory fallback.")
        collection = InMemoryRegStore()


def add_regulation_document(doc_id, text, metadata=None):
    """
    Adds regulatory document to vector store.
    """
    if metadata is None:
        metadata = {}
        
    collection.add(
        documents=[text],
        ids=[str(doc_id)],
        metadatas=[metadata]
    )

def retrieve_relevant_docs(query, n_results=2):
    """
    Retrieves relevant regulatory documents.
    """
    results = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    return results["documents"]

def seed_regulatory_knowledge_base():
    """
    Seeds the vector store with comprehensive BSA/AML regulatory documents if empty.
    """
    if collection.count() == 0:
        regulations = [
            {
                "id": "bsa_structuring",
                "text": "Structuring involves breaking down cash transactions into smaller sums to avoid reporting thresholds ($10,000). Patterns of deposits just below this limit are strong indicators. A series of transactions designed to evade the Currency Transaction Report (CTR) filing requirement constitutes structuring, which is a federal crime under 31 U.S.C. § 5324. Reference: 31 CFR § 1010.100(xx).",
                "source": "FFIEC BSA/AML Manual"
            },
            {
                "id": "bsa_layering",
                "text": "Layering is the process of separating criminal proceeds from their source by creating a complex web of financial transactions to disguise the audit trail and provide anonymity. This may involve multiple accounts, wire transfers, shell companies, and cross-border transactions designed to obscure the origin of funds.",
                "source": "FinCEN Guidance"
            },
            {
                "id": "sar_filing_deadline",
                "text": "A Suspicious Activity Report (SAR) must be filed with FinCEN within 30 days of initial detection of the suspicious activity. If no suspect is identified, the period is extended to 60 days. Continuing activity requires filing continuing SARs at least every 90 days. Reference: 31 CFR § 1020.320.",
                "source": "31 CFR § 1020.320"
            },
            {
                "id": "sar_narrative_requirements",
                "text": "The SAR narrative must include the five essential elements: Who is conducting the suspicious activity, What instruments or mechanisms are involved, When did the suspicious activity occur, Where did the activity take place, and Why does the activity appear suspicious. The narrative should also describe How the activity was conducted. Reference: FinCEN SAR Filing Instructions.",
                "source": "FinCEN SAR Filing Instructions"
            },
            {
                "id": "bsa_reporting_obligations",
                "text": "Financial institutions must file SARs for any transaction involving or aggregating at least $5,000 in funds or other assets when the institution knows, suspects, or has reason to suspect the transaction involves funds from illegal activities, is designed to evade BSA requirements, has no business or apparent lawful purpose, or facilitates criminal activity. Reference: 31 U.S.C. § 5318(g).",
                "source": "31 U.S.C. § 5318(g)"
            },
            {
                "id": "ctr_requirements",
                "text": "Currency Transaction Reports (CTRs) must be filed for each cash transaction exceeding $10,000. Multiple transactions by the same person on the same day that aggregate more than $10,000 must also be reported. Failure to file CTRs or structuring transactions to avoid them is a violation of the Bank Secrecy Act.",
                "source": "31 CFR § 1010.311"
            },
            {
                "id": "human_trafficking_indicators",
                "text": "Financial indicators of human trafficking include: large cash deposits followed by frequent and unusual ATM withdrawals, transactions inconsistent with expected activity, payments to online classified advertising, frequent wire transfers to certain geographic regions, and accounts controlled by a third party. FinCEN Advisory FIN-2020-A008 provides detailed guidance.",
                "source": "FinCEN Advisory FIN-2020-A008"
            },
            {
                "id": "money_laundering_typologies",
                "text": "Common money laundering typologies include: trade-based laundering using over/under-invoicing, real estate purchases with cash, use of shell companies and nominees, funnel accounts receiving deposits in one geographic area and withdrawing in another, and casino-related laundering. The FFIEC BSA/AML Examination Manual provides comprehensive typology descriptions.",
                "source": "FFIEC BSA/AML Manual"
            }
        ]
        
        for reg in regulations:
            add_regulation_document(reg["id"], reg["text"], {"source": reg["source"]})
        print(f"Knowledge Base Seeded with {len(regulations)} regulatory documents.")
