"""Tests for product CRUD, CSV upload, and flexible attributes."""
import pytest


@pytest.mark.asyncio
class TestProducts:

    async def test_create_product_minimal(self, client, auth_headers, test_tenant):
        """Only name and price required."""
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products",
            json={"name": "Simple Product", "price": "500.00"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Simple Product"
        assert data["source"] == "manual"

    async def test_create_product_with_custom_attributes(self, client, auth_headers, test_tenant):
        """Any extra fields become attributes."""
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products",
            json={
                "name": "Samsung A15",
                "price": "18000.00",
                "brand": "Samsung",
                "RAM": "6GB",
                "storage": "128GB",
                "color": "Blue",
                "warranty": "1 year",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Samsung A15"
        assert data["attributes"]["brand"] == "Samsung"
        assert data["attributes"]["RAM"] == "6GB"
        assert data["attributes"]["storage"] == "128GB"

    async def test_create_product_arabic_attributes(self, client, auth_headers, test_tenant):
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products",
            json={
                "name": "Cotton Galabiya",
                "price": "5000.00",
                "name_ar": "جلابية قطن",
                "category": "Clothing",
                "material": "cotton",
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["attributes"]["name_ar"] == "جلابية قطن"

    async def test_create_food_product(self, client, auth_headers, test_tenant):
        """Food products with completely different attributes."""
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products",
            json={
                "name": "Chocolate Cake",
                "price": "850",
                "flavor": "dark chocolate",
                "weight": "1kg",
                "serves": "8-10",
                "eggless": False,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        attrs = resp.json()["attributes"]
        assert attrs["flavor"] == "dark chocolate"
        assert attrs["weight"] == "1kg"

    async def test_list_products(self, client, auth_headers, test_tenant, test_products):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products", headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["products"]) == 3

    async def test_list_products_with_search(self, client, auth_headers, test_tenant, test_products):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products?search=Galabiya", headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_get_product_detail(self, client, auth_headers, test_tenant, test_products):
        product = test_products[0]
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products/{product.id}", headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Cotton Galabiya"
        assert data["attributes"]["material"] == "cotton"

    async def test_update_product_fixed_fields(self, client, auth_headers, test_tenant, test_products):
        product = test_products[0]
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/products/{product.id}",
            json={"price": "1800.00"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert float(resp.json()["price"]) == 1800.00

    async def test_update_product_custom_attributes(self, client, auth_headers, test_tenant, test_products):
        """Updating with new custom fields merges into attributes."""
        product = test_products[0]
        resp = await client.patch(
            f"/api/tenants/{test_tenant.id}/products/{product.id}",
            json={"color": "red", "new_field": "new_value"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        attrs = resp.json()["attributes"]
        assert attrs["color"] == "red"
        assert attrs["new_field"] == "new_value"
        # Original attributes preserved
        assert attrs["material"] == "cotton"

    async def test_delete_product(self, client, auth_headers, test_tenant, test_products):
        product = test_products[2]
        resp = await client.delete(
            f"/api/tenants/{test_tenant.id}/products/{product.id}", headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_csv_upload_standard(self, client, auth_headers, test_tenant):
        csv_content = "name,price,category,color\nT-Shirt,500,Clothing,red\nJeans,1200,Clothing,blue\n"
        import io
        files = {"file": ("products.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products/upload-csv",
            files=files,
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["detected_columns"]["name_column"] == "name"
        assert data["detected_columns"]["price_column"] == "price"
        assert "category" in data["detected_columns"]["attribute_columns"]
        assert "color" in data["detected_columns"]["attribute_columns"]

    async def test_csv_upload_alternative_column_names(self, client, auth_headers, test_tenant):
        """CSV with non-standard column names should still work."""
        csv_content = "product_name,cost,brand,weight\nRice 5kg,350,Miniket,5kg\nDal 1kg,180,Moshur,1kg\n"
        import io
        files = {"file": ("food.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products/upload-csv",
            files=files,
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 2
        assert data["detected_columns"]["name_column"] == "product_name"
        assert data["detected_columns"]["price_column"] == "cost"

    async def test_csv_upload_with_errors(self, client, auth_headers, test_tenant):
        csv_content = "name,price,category\n,500,Clothing\nGood Product,1000,Clothing\nBad,not_a_number,X\n"
        import io
        files = {"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products/upload-csv",
            files=files,
            headers={"Authorization": auth_headers["Authorization"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["imported"] == 1
        assert len(data["errors"]) >= 2

    async def test_csv_no_name_column(self, client, auth_headers, test_tenant):
        csv_content = "foo,bar\na,b\n"
        import io
        files = {"file": ("bad.csv", io.BytesIO(csv_content.encode()), "text/csv")}
        resp = await client.post(
            f"/api/tenants/{test_tenant.id}/products/upload-csv",
            files=files,
            headers={"Authorization": auth_headers["Authorization"]},
        )
        data = resp.json()
        assert data["imported"] == 0
        assert "No name column" in data["errors"][0]

    async def test_product_not_found(self, client, auth_headers, test_tenant):
        import uuid
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products/{uuid.uuid4()}", headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_pagination(self, client, auth_headers, test_tenant, test_products):
        resp = await client.get(
            f"/api/tenants/{test_tenant.id}/products?page=1&page_size=2", headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["products"]) == 2
        assert data["total"] == 3
