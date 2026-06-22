curl --location --request POST 'http://localhost:8016/recommendations/' \
--header 'x-api-key: foo' \
--header 'Content-Type: application/json' \
--data-raw '{
    "asset_name": "OIL",
    "datetime": "2023-03-22T09:00:00",
    "price": 72.3
}'