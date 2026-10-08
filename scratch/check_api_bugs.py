import urllib.request
import urllib.error
import json

def check_apis():
    print("=== CHECKING INVOICES ===")
    try:
        req = urllib.request.urlopen('http://127.0.0.1:8000/api/invoices')
        invs = json.loads(req.read().decode('utf-8'))
        print(f"Total invoices: {len(invs)}")
        flagged = [i for i in invs if i.get('status') in ['ESCALATED', 'BLOCKED', 'REJECTED']]
        print(f"Flagged invoices: {len(flagged)}")
        for f in flagged[:3]:
            iid = f['id']
            inv_num = f.get('invoice_number')
            st = f.get('status')
            print(f"Checking {inv_num} ({iid}) - status: {st}")
            try:
                r1 = urllib.request.urlopen(f"http://127.0.0.1:8000/api/invoices/{iid}")
                print(f"  GET /api/invoices/{iid} -> {r1.status}")
            except Exception as e:
                print(f"  GET /api/invoices/{iid} -> FAILED: {e}")
            try:
                r2 = urllib.request.urlopen(f"http://127.0.0.1:8000/api/invoices/{iid}/risk-assessment")
                print(f"  GET /api/invoices/{iid}/risk-assessment -> {r2.status}")
            except Exception as e:
                print(f"  GET /api/invoices/{iid}/risk-assessment -> FAILED: {e}")
            try:
                r3 = urllib.request.urlopen(f"http://127.0.0.1:8000/api/invoices/{iid}/ai-evaluations")
                print(f"  GET /api/invoices/{iid}/ai-evaluations -> {r3.status}")
            except Exception as e:
                print(f"  GET /api/invoices/{iid}/ai-evaluations -> FAILED: {e}")
    except Exception as e:
        print("Failed to query /api/invoices:", e)

    print("\n=== CHECKING VENDORS ===")
    try:
        req = urllib.request.urlopen('http://127.0.0.1:8000/api/vendors')
        body = req.read().decode('utf-8')
        print(f"GET /api/vendors -> {req.status}")
        print("Body snippet:", body[:200])
        vendors = json.loads(body)
        print(f"Total vendors: {len(vendors)}")
        if vendors:
            print("First vendor sample keys:", list(vendors[0].keys()))
            print("First vendor sample:", vendors[0])
    except urllib.error.HTTPError as e:
        print(f"GET /api/vendors HTTPError: {e.code} - {e.read().decode('utf-8', errors='replace')}")
    except Exception as e:
        print("GET /api/vendors Error:", e)

    print("\n=== CHECKING INVESTIGATIONS ===")
    try:
        req = urllib.request.urlopen('http://127.0.0.1:8000/api/investigations')
        print("GET /api/investigations ->", req.status)
    except urllib.error.HTTPError as e:
        print(f"GET /api/investigations HTTPError: {e.code} - {e.read().decode('utf-8', errors='replace')}")
    except Exception as e:
        print("GET /api/investigations Error:", e)

if __name__ == "__main__":
    check_apis()
