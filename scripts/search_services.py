
import json
from pathlib import Path

from sentence_transformers import SentenceTransformer, util

# Locate the project and dataset.
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = PROJECT_DIR / "data" / "db_for_voice.json"

# A multilingual model that supports German and English.
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def load_services():
    """Load services from the existing JSON dataset."""
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def create_service_text(service):
    """Combine the important text fields for searching."""
    title = service.get("title_de") or ""
    description = service.get("description_raw") or ""

    return f"{title}. {description}"


def search_services(query, services, model, service_embeddings, limit=5):
    """Find services that are semantically similar to the query."""
    query_embedding = model.encode(
        query,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    similarities = util.cos_sim(query_embedding, service_embeddings)[0]
    top_results = similarities.argsort(descending=True)[:limit]

    results = []

    for index in top_results:
        service = services[index.item()]
        score = similarities[index].item()
        results.append((score, service))

    return results


def main():
    services = load_services()

    # Prepare text for every service.
    service_texts = [create_service_text(s) for s in services]

    print(f"Loaded {len(services)} Caritas services.")
    print("Loading multilingual embedding model...")

    model = SentenceTransformer(MODEL_NAME)

    print("Creating service embeddings...")
    service_embeddings = model.encode(
        service_texts,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )

    print("\nSemantic search is ready!")
    print("Ask in German or English. Type 'exit' to stop.\n")

    while True:
        query = input("Your question: ").strip()

        if query.lower() == "exit":
            break

        if not query:
            continue

        results = search_services(
            query,
            services,
            model,
            service_embeddings,
        )

        print("\nMost similar services:")

        for score, service in results:
            print(f"\nService: {service.get('title_de', 'Unknown')}")
            print(f"Similarity: {score:.3f}")
            print(
                "Description:",
                service.get("description_raw") or "No description available",
            )
            print("Website:", service.get("url") or "No website available")

        print()


if __name__ == "__main__":
    main()
