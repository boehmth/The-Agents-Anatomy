import requests
import random
import json

FAKE_STORE_URL = "https://fakestoreapi.com/products"

def fetch_fake_store_products():
    """Ruft die Produktliste von Fake Store API ab."""
    r = requests.get(FAKE_STORE_URL, timeout=10)
    r.raise_for_status()
    return r.json()

def sample_order_from_products(products, n_items=5):
    """Erzeugt eine Beispiel-Bestellliste als dict {title: qty}."""
    sample = random.sample(products, min(n_items, len(products)))
    order = {}
    for p in sample:
        order[p["title"]] = random.randint(1, 100)
    return order

def main(n_items: int = 15):
    """
    Lädt Produkte von Fake Store API, erzeugt eine zufällige Bestellliste
    und gibt sie als JSON auf stdout aus.
    """
    products = fetch_fake_store_products()
    order = sample_order_from_products(products, n_items=n_items)
    print(json.dumps(order, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    # Beispiel: main(6) erzeugt eine Liste mit 6 zufälligen Artikeln
    main()
