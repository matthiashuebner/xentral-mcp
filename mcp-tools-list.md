# Xentral MCP Tools

Auto-generated from the [official Xentral OpenAPI spec](https://raw.githubusercontent.com/xentral/api-spec-public/main/openapi/xentral-api.openapi-3.0.0.json).
**339 API tools** across 74 resource groups, plus the hand-written convenience tools in `xentral/`.

Regenerate with: `python scripts/generate_catalog.py`

## Account (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `account_create_v1` | `POST /api/v1/account` | 🔒 Create account |
| `account_delete_v1` | `DELETE /api/v1/account/{id}` | 🔒 Delete Account Entry by ID |
| `account_get_v1` | `GET /api/v1/account/{id}` | 🔒 Get Account Entry by ID |
| `account_list_v1` | `GET /api/v1/account` | 🔒 List Account Entries |
| `account_update_v1` | `PATCH /api/v1/account/{id}` | 🔒 Update account |

## Accounting Export (8 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `accounting_datev_csv_export_account_transactions` | `POST /api/v1/accounting/datev/csvExport/accountTransactions` | Execute the accounting CSV export for account transactions |
| `accounting_datev_csv_export_invoices_and_credit_notes` | `POST /api/v1/accounting/datev/csvExport/invoicesAndCreditNotes` | Execute the accounting CSV export for invoices and credit notes |
| `accounting_datev_csv_export_liabilities` | `POST /api/v1/accounting/datev/csvExport/liabilities` | Execute the accounting CSV export for liabilities |
| `accounting_datev_download` | `GET /api/v1/accounting/downloads/{downloadKey}` | Download accounting export |
| `accounting_datev_download_status` | `GET /api/v1/accounting/downloads/{downloadKey}/status` | Check accounting export status |
| `accounting_datev_xml_export_credit_notes` | `POST /api/v1/accounting/datev/xmlExport/creditNotes` | Execute the accounting XML export for credit notes |
| `accounting_datev_xml_export_invoices` | `POST /api/v1/accounting/datev/xmlExport/invoices` | Execute the accounting XML export for invoices |
| `accounting_datev_xml_export_liabilities` | `POST /api/v1/accounting/datev/xmlExport/liabilities` | Execute the accounting XML export for liabilities |

## AuthPlatform (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `auth_platform_exchange_token` | `POST /api/v1/auth-platform/token-exchange` | Exchange subject token for platform access token |

## Collection (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `analytics_collection_create` | `POST /api/v1/analytics/collection` | Create collection |
| `analytics_collection_delete` | `DELETE /api/v1/analytics/collection/{id}` | Delete collection |
| `analytics_collection_get` | `GET /api/v1/analytics/collection` | List collections |
| `analytics_collection_list` | `GET /api/v1/analytics/collection/{id}` | View collection |
| `analytics_collection_update` | `PATCH /api/v1/analytics/collection/{id}` | Update collection |

## Collective Bill (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `collective_bill_create` | `POST /api/v1/collectiveBill` | Create collective bill |

## Credit (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `analytics_credit_get` | `GET /api/v1/analytics/credit` | Get credit information |

## Credit Note (7 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `credit_note_balance` | `GET /api/v1/creditNotes/{id}/balance` | View Credit Note Balance |
| `credit_note_create` | `POST /api/v1/creditNotes` | Create credit note |
| `credit_note_documents_view` | `GET /api/v1/creditNotes/{id}/documents` | View related documents for credit note |
| `credit_note_list` | `GET /api/v1/creditNotes` | List credit notes |
| `credit_note_send` | `PATCH /api/v1/creditNotes/{id}/actions/send` | Send credit note |
| `credit_note_update` | `PATCH /api/v1/creditNotes/{id}` | Update credit note |
| `credit_note_view` | `GET /api/v1/creditNotes/{id}` | View credit note |

## Credit Note Tag (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `credit_note_tag_list` | `GET /api/v1/creditNotesTags` | List Credit Notes tags ⚠️ deprecated |

## Customer (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `customer_create_v2` | `POST /api/v2/customers` | Create customer |
| `customer_delete` | `DELETE /api/v1/customers/{id}` | Delete customer |
| `customer_list_v2` | `GET /api/v2/customers` | List customers |
| `customer_update_v2` | `PATCH /api/v2/customers/{id}` | Update customer |
| `customer_view_v2` | `GET /api/v2/customers/{id}` | View customer |

## Customer - Contact Person (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `customer_contact_person_create` | `POST /api/v1/customers/{customerId}/contactPerson` | Create contact person |
| `customer_contact_person_delete` | `DELETE /api/v1/customers/{customerId}/contactPerson/{contactPersonId}` | Delete contact person |
| `customer_contact_person_get` | `GET /api/v1/customers/{customerId}/contactPerson/{contactPersonId}` | View contact person |
| `customer_contact_person_get_list` | `GET /api/v1/customers/{customerId}/contactPerson` | List contact persons |
| `customer_contact_person_update` | `PATCH /api/v1/customers/{customerId}/contactPerson/{contactPersonId}` | Update contact person |

## Customer Address (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `customer_address_create_v2` | `POST /api/v2/customers/{customerId}/addresses` | Create address |
| `customer_address_delete_v2` | `DELETE /api/v2/customers/{customerId}/addresses/{id}` | Delete address |
| `customer_address_list_v2` | `GET /api/v2/customers/{customerId}/addresses` | List addresses |
| `customer_address_update_v2` | `PATCH /api/v2/customers/{customerId}/addresses/{id}` | Update address |
| `customer_address_view_v2` | `GET /api/v2/customers/{customerId}/addresses/{id}` | View address |

## Delivery (3 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `deliveries_list` | `GET /api/v1/deliveries` | List deliveries |
| `delivery_view` | `GET /api/v1/deliveries/{id}` | View delivery ⚠️ deprecated |
| `shipment_view` | `GET /api/v1/shipments/{id}` | View shipment |

## Delivery Note (6 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `delivery_note_deliveries_list` | `GET /api/v1/deliveryNotes/{id}/deliveries` | List delivery note deliveries ⚠️ deprecated |
| `delivery_note_list` | `GET /api/v1/deliveryNotes` | List delivery notes |
| `delivery_note_positions_customs_update` | `PATCH /api/v1/deliveryNotes/{id}/customsUpdate` | Update delivery note positions customs data. |
| `delivery_note_shipments_list` | `GET /api/v1/deliveryNotes/{id}/shipments` | View delivery note shipments |
| `delivery_note_view` | `GET /api/v1/deliveryNotes/{id}` | View delivery note |
| `delivery_notes_assign_quality_control_attributes` | `PATCH /api/v1/deliveryNotes/{id}/actions/assignQualityControlAttributes` | Assign quality control attributes to delivery note |

## Delivery Note Tag (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `delivery_note_tag_list` | `GET /api/v1/deliveryNotesTags` | List delivery notes tags ⚠️ deprecated |

## Delivery Terms (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `delivery_terms_list` | `GET /api/v1/deliveryTerms` | List delivery terms |

## Documentation (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `analytics_documentation_list` | `GET /api/v1/analytics/documentation` | List documentations |

## Employee (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `employee_list` | `GET /api/v1/employees` | List employees |

## External Reference (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `external_reference_create` | `POST /api/v1/products/{id}/externalReferences` | Create external reference |
| `external_reference_delete_multiple` | `DELETE /api/v1/products/{id}/externalReferences` | Delete external reference |
| `external_reference_list` | `GET /api/v1/products/{id}/externalReferences` | List external references |
| `external_reference_update_multiple` | `PATCH /api/v1/products/{id}/externalReferences` | Update external reference |

## External Reference Target (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `external_reference_target_list` | `GET /api/v1/externalReferenceTargets` | List external reference targets |

## File (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `files_list` | `GET /api/v2/{documentType}/{id}/files` | List files for a document |
| `files_view` | `GET /api/v2/{documentType}/{id}/files/{fileId}` | View file of a document by id |

## General Ledger (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `general_ledger_get_v1` | `GET /api/v1/generalLedger/{id}` | 🔒 Get General Ledger Entry by ID |
| `general_ledger_list` | `GET /api/v1/generalLedger` | 🔒 List General Ledger Entries |
| `general_ledger_list_with_aggregated_account` | `GET /api/v1/generalLedgerAggAccountView` | 🔒 List General Ledger Entries With Aggregated Account |
| `general_ledger_list_with_aggregated_document` | `GET /api/v1/generalLedgerAggDocumentView` | 🔒 List General Ledger Entries With Aggregated Document |
| `general_ledger_list_with_aggregated_line_item` | `GET /api/v1/generalLedgerAggLineItemView` | 🔒 List General Ledger Entries With Aggregated Line Item |

## Goods Receipt (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `purchase_order_goods_receipt_create` | `POST /api/v1/purchaseOrders/{id}/goodsReceipts` | Create goods receipt for purchase order |
| `return_goods_receipt_create` | `POST /api/v1/returns/{id}/goodsReceipts` | Create goods receipt for return |

## Invoice (10 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `invoice_balance` | `GET /api/v1/invoices/{id}/balance` | View invoice balance |
| `invoice_create` | `POST /api/v1/invoices` | Create invoice |
| `invoice_create_positions` | `POST /api/v1/invoices/{id}/positions` | Create positions for invoice |
| `invoice_documents_view` | `GET /api/v1/invoices/{id}/documents` | View related documents for invoice |
| `invoice_list` | `GET /api/v1/invoices` | List invoices |
| `invoice_send` | `PATCH /api/v1/invoices/{id}/send` | Send invoice ⚠️ deprecated |
| `invoice_send_v2` | `PATCH /api/v2/invoices/{id}/actions/send` | Send invoice V2 |
| `invoice_status` | `PATCH /api/v1/invoices/{id}/status` | Update status for single invoice |
| `invoice_update` | `PATCH /api/v1/invoices/{id}` | Update invoice |
| `invoice_view` | `GET /api/v1/invoices/{id}` | View invoice |

## Invoice Tag (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `invoice_tag_list` | `GET /api/v1/invoicesTags` | List Invoice tags ⚠️ deprecated |

## Liability (6 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `liability_actions_release` | `PATCH /api/v1/liabilities/{id}/actions/release` | Release liability |
| `liability_create` | `POST /api/v1/liabilities` | Create liability |
| `liability_create_recurring` | `POST /api/v1/liabilities-recurring` | Create recurring liability |
| `liability_document_upload` | `POST /api/v1/liabilities/{id}/documents` | Add file to liability |
| `liability_list` | `GET /api/v1/liabilities` | List liabilities |
| `liability_view` | `GET /api/v1/liabilities/{id}` | View liability |

## Matrixproduct (11 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_create_multiple_values` | `POST /api/v1/products/{productId}/options/{id}/values` | Create multiple product option values |
| `product_create_option` | `POST /api/v1/products/{id}/options` | Create product option |
| `product_delete_multiple_options` | `DELETE /api/v1/products/{id}/options` | Delete multiple product options |
| `product_delete_multiple_values` | `DELETE /api/v1/products/{productId}/options/{id}/values` | Delete multiple product option values |
| `product_delete_value` | `DELETE /api/v1/products/{productId}/options/{optionId}/values/{id}` | Delete product option value |
| `product_list_options` | `GET /api/v1/products/{id}/options` | List product options |
| `product_list_values` | `GET /api/v1/products/{productId}/options/{id}/values` | List product option values |
| `product_update_multiple_options` | `PATCH /api/v1/products/{id}/options` | Update multiple product options |
| `product_update_option` | `PATCH /api/v1/products/{productId}/options/{id}` | Update product option |
| `product_update_value` | `PATCH /api/v1/products/{productId}/options/{optionId}/values/{id}` | Update product option value |
| `product_view_value` | `GET /api/v1/products/{productId}/options/{optionId}/values/{id}` | View product option value |

## Payment Methods (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `payment_method_list` | `GET /api/v1/paymentMethods` | List payment methods |

## Payment Service Provider (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `payment_service_provider_transaction_create_v1` | `POST /api/v1/paymentServiceProviders/{id}/transactions` | Create payment service provider transactions |
| `payment_service_provider_transaction_list_v1` | `GET /api/v1/paymentServiceProviders/{id}/transactions` | List payment service provider transactions |

## Payment Terms Group (3 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `payment_terms_group_create` | `POST /api/v1/paymentTermsGroups` | Create payment terms group |
| `payment_terms_group_list` | `GET /api/v1/paymentTermsGroups` | List payment terms groups |
| `payment_terms_group_view` | `GET /api/v1/paymentTermsGroups/{id}` | View payment terms group |

## Payment Transaction (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `payment_transaction_status` | `PATCH /api/v1/paymentTransactions/{id}/status` | Update payment transaction status |
| `payment_transaction_view` | `GET /api/v1/paymentTransactions/{id}` | View payment transaction |

## Point Of Sale (7 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `cash_count_add` | `POST /api/v1/posCashCount/actions/add` | Add cash count entry |
| `cash_register_balance` | `GET /api/v1/cashRegisters/{id}/balance` | View cash register balance |
| `cashier_list` | `GET /api/v1/cashiers` | List cashiers |
| `cashier_pin_check` | `POST /api/v1/cashiers/{id}/pinCheck` | Cashier PIN check |
| `journal_add` | `POST /api/v1/posJournals/actions/add` | Add journal entry |
| `journal_list` | `GET /api/v1/posJournals` | List POS journals |
| `qr_code_add` | `POST /api/v1/posQrCode/actions/add` | Add qr code data to a document |

## Print Jobs (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `print_jobs_create` | `POST /api/v1/printJobs` | Create print job |

## Product (37 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_create` | `POST /api/v1/products` | Create new product V1 ⚠️ deprecated |
| `product_create_cross_selling_products` | `POST /api/v1/products/{id}/crossSelling` | Create cross selling |
| `product_create_parts` | `POST /api/v1/products/{id}/parts` | Create parts v1 ⚠️ deprecated |
| `product_create_parts_v2` | `POST /api/v2/products/{id}/parts` | Create parts v2 |
| `product_create_v2` | `POST /api/v2/products` | Create product V2 |
| `product_create_variants` | `POST /api/v1/products/{id}/actions/createVariants` | Creates variants for a matrix product |
| `product_delete` | `DELETE /api/v1/products/{id}` | Delete product |
| `product_delete_cross_selling` | `DELETE /api/v1/products/{id}/crossSelling` | Delete cross selling |
| `product_delete_multiple` | `DELETE /api/v1/products` | Delete multiple products |
| `product_delete_parts` | `DELETE /api/v1/products/{id}/parts` | Delete parts |
| `product_identify_product` | `GET /api/v1/products/actions/identify` | Identify product ⚠️ deprecated |
| `product_list` | `GET /api/v1/products` | List products V1 ⚠️ deprecated |
| `product_list_cross_selling` | `GET /api/v1/products/{id}/crossSelling` | List cross sellings |
| `product_list_media` | `GET /api/v1/products/{id}/media` | View media ⚠️ deprecated |
| `product_list_parts` | `GET /api/v1/products/{id}/parts` | List parts |
| `product_list_productions_positions` | `GET /api/v1/products/{id}/productionsPositions` | View productions positions |
| `product_list_properties` | `GET /api/v1/products/{id}/properties` | List product properties |
| `product_list_purchase_orders_positions` | `GET /api/v1/products/{id}/purchaseOrdersPositions` | View purchase orders positions |
| `product_list_purchase_prices` | `GET /api/v1/products/{id}/purchasePrices` | View purchase prices |
| `product_list_reservations` | `GET /api/v1/products/{id}/reservations` | View reservations |
| `product_list_sales_orders_positions` | `GET /api/v1/products/{id}/salesOrdersPositions` | View sales orders positions |
| `product_list_sales_prices` | `GET /api/v1/products/{id}/salesPrices` | View sales prices |
| `product_list_texts` | `GET /api/v1/products/{id}/texts` | List product texts |
| `product_list_v2` | `GET /api/v2/products` | List products V2 |
| `product_storage_locations` | `GET /api/v1/products/{id}/storageLocations` | View storage locations |
| `product_update` | `PATCH /api/v1/products/{id}` | Update product v1 ⚠️ deprecated |
| `product_update_account_mapping` | `PATCH /api/v1/products/{id}/updateAccountMapping` | Update account mapping |
| `product_update_cross_selling_products` | `PATCH /api/v1/products/{id}/crossSelling` | Update cross selling |
| `product_update_multiple` | `PATCH /api/v1/products` | Update multiple products V1 ⚠️ deprecated |
| `product_update_multiple_v2` | `PATCH /api/v2/products` | Update multiple products V2 |
| `product_update_parts` | `PATCH /api/v1/products/{id}/parts` | Update parts v1 ⚠️ deprecated |
| `product_update_parts_v2` | `PATCH /api/v2/products/{id}/parts` | Update parts v2 |
| `product_update_properties` | `PATCH /api/v1/products/{id}/properties` | Update product properties |
| `product_update_v2` | `PATCH /api/v2/products/{id}` | Update product v2 |
| `product_view` | `GET /api/v1/products/{id}` | View product v1 ⚠️ deprecated |
| `product_view_stocks` | `GET /api/v1/products/{id}/stocks` | View stock details of a product |
| `product_view_v2` | `GET /api/v2/products/{id}` | View product V2 |

## Product Category (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_category_create` | `POST /api/v1/productsCategories` | Create product category |
| `product_category_delete` | `DELETE /api/v1/productsCategories/{id}` | Delete product category |
| `product_category_list` | `GET /api/v1/productsCategories` | List product categories |
| `product_category_update` | `PATCH /api/v1/productsCategories/{id}` | Update product category |
| `product_category_view` | `GET /api/v1/productsCategories/{id}` | View product category |

## Product Free Field (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_free_field_list` | `GET /api/v1/productsFreeFields` | List product free fields |
| `product_free_field_update` | `PATCH /api/v1/productsFreeFields/{id}` | Update product free field |
| `product_free_field_update_multiple` | `PATCH /api/v1/productsFreeFields` | Update multiple product free fields |
| `product_free_field_view` | `GET /api/v1/productsFreeFields/{id}` | View product free field |

## Product Label (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_label_download` | `GET /api/v1/products/{id}/printLabel` | Download product label as pdf |
| `product_label_print` | `POST /api/v1/products/{id}/printLabel` | Print product label |

## Product Media (9 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_media_create` | `POST /api/v1/productMedia` | Create product media |
| `product_media_create_version` | `POST /api/v1/productMedia/{id}/versions` | Create product media version |
| `product_media_delete_multiple` | `DELETE /api/v1/productMedia` | Delete multiple product media |
| `product_media_delete_version` | `DELETE /api/v1/productMedia/{id}/versions/{version}` | Delete product media version |
| `product_media_list` | `GET /api/v1/productMedia` | List product media |
| `product_media_update_multiple` | `PATCH /api/v1/productMedia` | Update multiple product media |
| `product_media_update_version` | `PATCH /api/v1/productMedia/{id}/versions/{version}` | Update product media version |
| `product_media_view` | `GET /api/v1/productMedia/{id}` | View product media |
| `product_media_view_version` | `GET /api/v1/productMedia/{id}/versions/{version}` | View product media version |

## Product Merchandise Group (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_merchandise_group_create` | `POST /api/v1/productsMerchandiseGroups` | Create product merchandise group |
| `product_merchandise_group_delete` | `DELETE /api/v1/productsMerchandiseGroups/{id}` | Delete product merchandise group |
| `product_merchandise_group_list` | `GET /api/v1/productsMerchandiseGroups` | List product merchandise groups |
| `product_merchandise_group_update` | `PATCH /api/v1/productsMerchandiseGroups/{id}` | Update product merchandise group |
| `product_merchandise_group_view` | `GET /api/v1/productsMerchandiseGroups/{id}` | View product merchandise group |

## Product Property (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_property_create` | `POST /api/v1/productsProperties` | Create multiple product properties |
| `product_property_delete_multiple` | `DELETE /api/v1/productsProperties` | Delete multiple product properties |
| `product_property_list` | `GET /api/v1/productsProperties` | List product properties |
| `product_property_update_multiple` | `PATCH /api/v1/productsProperties` | Update multiple product properties |

## Product Tag (3 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_tag_create` | `POST /api/v1/productsTags` | Create product tag ⚠️ deprecated |
| `product_tag_list` | `GET /api/v1/productsTags` | List product tags ⚠️ deprecated |
| `product_tag_update` | `PATCH /api/v1/productsTags/{id}` | Update product tag ⚠️ deprecated |

## Production (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `production_actions_cancel` | `PATCH /api/v1/productions/{id}/actions/cancel` | Cancel production |
| `production_actions_release` | `PATCH /api/v1/productions/{id}/actions/release` | Release production |
| `production_list` | `GET /api/v1/productions` | List productions |
| `production_view` | `GET /api/v1/productions/{id}` | View production |

## Project (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `project_list` | `GET /api/v1/projects` | List projects |
| `project_pos_settings` | `GET /api/v1/projects/{id}/posSettings` | List POS settings for project |

## Provisional Return (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `provisional_returns_list` | `GET /api/v1/provisionalReturns` | List provisional returns |

## Purchase Order (6 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `purchase_order_actions_cancel` | `PATCH /api/v1/purchaseOrders/{id}/actions/cancel` | Cancel purchase order |
| `purchase_order_actions_release` | `PATCH /api/v1/purchaseOrders/{id}/actions/release` | Release purchase order |
| `purchase_order_create` | `POST /api/v1/purchaseOrders` | Create purchase order |
| `purchase_order_list` | `GET /api/v1/purchaseOrders` | List purchase orders |
| `purchase_order_update` | `PATCH /api/v1/purchaseOrders/{id}` | Update purchase order |
| `purchase_order_view` | `GET /api/v1/purchaseOrders/{id}` | View purchase order |

## Purchase Price (10 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `purchase_price_create` | `POST /api/v1/purchasePrices` | Create purchase price V1 ⚠️ deprecated |
| `purchase_price_create_v2` | `POST /api/v2/purchasePrices` | Create purchase price V2 |
| `purchase_price_delete` | `DELETE /api/v1/purchasePrices/{id}` | Delete purchase price |
| `purchase_price_list` | `GET /api/v1/purchasePrices` | List purchase prices V1 ⚠️ deprecated |
| `purchase_price_list_v2` | `GET /api/v2/purchasePrices` | List purchase prices V2 |
| `purchase_price_update` | `PATCH /api/v1/purchasePrices/{id}` | Update purchase price V1 ⚠️ deprecated |
| `purchase_price_update_multiple` | `PATCH /api/v1/purchasePrices` | Update multiple purchase prices V1 ⚠️ deprecated |
| `purchase_price_update_multiple_v2` | `PATCH /api/v2/purchasePrices` | Update multiple purchase prices V2 |
| `purchase_price_update_v2` | `PATCH /api/v2/purchasePrices/{id}` | Update purchase price V2 |
| `purchase_price_view` | `GET /api/v1/purchasePrices/{id}` | View purchase price |

## Query (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `analytics_query` | `POST /api/v1/analytics/query` | Execute query |
| `analytics_query_export_create` | `POST /api/v1/analytics/query/export` | Create query export |
| `analytics_query_export_get_by_id` | `GET /api/v1/analytics/query/export/{uuid}` | View query export |
| `analytics_query_export_list` | `GET /api/v1/analytics/query/export` | List query exports |

## Report (18 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `analytics_report_create` | `POST /api/v1/analytics/report` | Create report |
| `analytics_report_delete` | `DELETE /api/v1/analytics/report/{id}` | Delete report |
| `analytics_report_export_create` | `POST /api/v1/analytics/report/{id}/export` | Create report export |
| `analytics_report_export_get_by_id` | `GET /api/v1/analytics/report/{id}/export/{uuid}` | View report export |
| `analytics_report_export_list` | `GET /api/v1/analytics/report/{id}/export` | List report exports |
| `analytics_report_get` | `GET /api/v1/analytics/report/{id}` | View report |
| `analytics_report_list` | `GET /api/v1/analytics/report` | List reports |
| `analytics_report_permalink_create` | `POST /api/v1/analytics/report/{id}/permalink` | Create report permalink |
| `analytics_report_permalink_delete` | `DELETE /api/v1/analytics/report/{id}/permalink` | Invalidate permalink for report |
| `analytics_report_permalink_download` | `GET /api/v1/analytics/report/{id}/permalink/{token}` | Download report |
| `analytics_report_permalink_get` | `GET /api/v1/analytics/report/{id}/permalink` | List report permalink |
| `analytics_report_query` | `POST /api/v1/analytics/report/{id}/query` | Execute report query |
| `analytics_report_schedule_create` | `POST /api/v1/analytics/report/{id}/schedule` | Create report schedule |
| `analytics_report_schedule_delete` | `DELETE /api/v1/analytics/report/{id}/schedule/{uuid}` | Delete report schedule |
| `analytics_report_schedule_list` | `GET /api/v1/analytics/report/{id}/schedule` | List report schedules |
| `analytics_report_schedule_update` | `PATCH /api/v1/analytics/report/{id}/schedule/{uuid}` | Update report schedule |
| `analytics_report_update` | `PATCH /api/v1/analytics/report/{id}` | Update report |
| `analytics_schedule_list` | `GET /api/v1/analytics/schedule` | List schedules |

## Report Usage (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `analytics_report_usage_get` | `GET /api/v1/analytics/reportUsage` | Get report usage |

## Reporting Settings (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `analytics_settings_get` | `GET /api/v1/analytics/settings` | Get settings |
| `analytics_settings_update` | `PATCH /api/v1/analytics/settings` | Update reporting settings |

## Return (9 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `return_actions_release` | `POST /api/v1/returns/{id}/actions/release` | Release return |
| `return_create` | `POST /api/v1/returns` | Create return |
| `return_create_document` | `POST /api/v1/returns/{id}/documents` | Create return document |
| `return_delete_multiple` | `DELETE /api/v1/returns/{id}/documents` | Delete multiple return documents |
| `return_list` | `GET /api/v1/returns` | List returns |
| `return_list_document` | `GET /api/v1/returns/{id}/documents` | List return documents ⚠️ deprecated |
| `return_update_multiple` | `PATCH /api/v1/returns/{id}/documents` | Update multiple return documents |
| `return_view` | `GET /api/v1/returns/{id}` | View return |
| `return_view_document` | `GET /api/v1/returns/{id}/documents/{documentId}` | View return document ⚠️ deprecated |

## Return Reason (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `return_reason_list` | `GET /api/v1/returnReasons` | List return reasons |

## Revenue Account Mapping (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `revenue_account_mapping_create_v1` | `POST /api/v1/revenueAccountMapping` | 🔒 Create revenue account mapping |
| `revenue_account_mapping_delete_v1` | `DELETE /api/v1/revenueAccountMapping/{id}` | 🔒 Delete Revenue Account Mapping Entry by ID |
| `revenue_account_mapping_get_v1` | `GET /api/v1/revenueAccountMapping/{id}` | 🔒 Get Revenue Account Mapping Entry by ID |
| `revenue_account_mapping_list_v1` | `GET /api/v1/revenueAccountMapping` | 🔒 List Revenue Account Mapping Entries |
| `revenue_account_mapping_update_v1` | `PATCH /api/v1/revenueAccountMapping/{id}` | 🔒 Update revenue account mapping |

## Sales Channel (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `sales_channel_list_v2` | `GET /api/v2/salesChannels` | List sales channels V2 |

## Sales Channels Product Settings (3 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `product_create_sales_channels` | `POST /api/v1/products/{id}/salesChannels` | Create product sales channel settings |
| `product_delete_sales_channels` | `DELETE /api/v1/products/{productId}/salesChannels/{id}` | Delete product sales channel settings |
| `product_update_sales_channels` | `PATCH /api/v1/products/{productId}/salesChannels/{id}` | Update product sales channel settings |

## Sales Order (13 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `sales_order_actions_cancel` | `POST /api/v1/salesOrders/{id}/actions/cancel` | Cancel sales order |
| `sales_order_actions_create_partial_sales_order` | `PATCH /api/v1/salesOrders/{id}/actions/createPartialSalesOrder` | Create partial sales order |
| `sales_order_actions_dispatch` | `POST /api/v1/salesOrders/{id}/actions/dispatch` | Dispatch sales order |
| `sales_order_create_document` | `POST /api/v1/salesOrders/{id}/documents` | Create sales order document |
| `sales_order_delete` | `DELETE /api/v1/salesOrders/{id}` | Delete sales order |
| `sales_order_delete_multiple` | `DELETE /api/v1/salesOrders/{id}/documents` | Delete multiple sales order documents |
| `sales_order_import` | `POST /api/v1/salesOrders/actions/import` | Import sales order |
| `sales_order_list` | `GET /api/v1/salesOrders` | List sales orders |
| `sales_order_list_document` | `GET /api/v1/salesOrders/{id}/documents` | List sales order documents ⚠️ deprecated |
| `sales_order_update` | `PATCH /api/v1/salesOrders/{id}` | Update sales order |
| `sales_order_update_multiple` | `PATCH /api/v1/salesOrders/{id}/documents` | Update multiple sales order documents |
| `sales_order_view` | `GET /api/v1/salesOrders/{id}` | View sales order |
| `sales_order_view_document` | `GET /api/v1/salesOrders/{id}/documents/{documentId}` | View sales order document ⚠️ deprecated |

## Sales Price (6 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `sales_price_create` | `POST /api/v1/salesPrices` | Create sales price |
| `sales_price_delete` | `DELETE /api/v1/salesPrices/{id}` | Delete sales price |
| `sales_price_list` | `GET /api/v1/salesPrices` | List sales prices |
| `sales_price_update` | `PATCH /api/v1/salesPrices/{id}` | Update sales price |
| `sales_price_update_multiple` | `PATCH /api/v1/salesPrices` | Update multiple sales prices |
| `sales_price_view` | `GET /api/v1/salesPrices/{id}` | View sales price |

## Setting (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `settings_masterdata_address_custom_fields_create_v1` | `POST /api/v2/settings/masterdata/addressCustomFields` | Create address free field |
| `settings_masterdata_address_custom_fields_list_v2` | `GET /api/v2/settings/masterdata/addressCustomFields` | List address free fields |
| `settings_text_templates_v2` | `GET /api/v2/settings/text-templates` | List text templates |
| `settings_text_templates_v2_update` | `PATCH /api/v2/settings/text-templates` | Update text templates |

## Shipments (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `shipments_create` | `POST /api/v1/shipments` | Create tracking information |

## Shipping Methods (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `shipping_method_create` | `POST /api/v1/shippingMethods` | Create shipping method |
| `shipping_method_list` | `GET /api/v1/shippingMethods` | List shipping methods |
| `shipping_method_update` | `PUT /api/v1/shippingMethods/{id}` | Update shipping method |
| `shipping_method_view` | `GET /api/v1/shippingMethods/{id}` | View shipping method |

## Stock Movement Types (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `stock_movement_type_create` | `POST /api/v1/stockMovementTypes` | Create stock movement type |

## Storage Item (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `storage_item_list` | `GET /api/v1/warehouses/{warehouseId}/storageLocations/{storageLocationId}/items` | List storage items V1 ⚠️ deprecated |
| `storage_location_list_v2` | `GET /api/v2/warehouses/{warehouseId}/storageLocations/{storageLocationId}/items` | List storage items V2 |
| `warehouse_retrieve_item` | `PATCH /api/v1/warehouses/{warehouseId}/storageLocations/{storageLocationId}/items` | Retrieve item from storage location |
| `warehouse_stock_item` | `POST /api/v1/warehouses/{warehouseId}/storageLocations/{storageLocationId}/items` | Add item to storage location |

## Storage Location (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `storage_location_create` | `POST /api/v1/warehouses/{warehouseId}/storageLocations` | Create storage location |
| `storage_location_delete` | `DELETE /api/v1/warehouses/{warehouseId}/storageLocations/{storageLocationId}` | Delete storage location |
| `storage_location_list` | `GET /api/v1/warehouses/{warehouseId}/storageLocations` | List storage locations |
| `storage_location_update` | `PATCH /api/v1/warehouses/{warehouseId}/storageLocations/{storageLocationId}` | Update storage location |
| `storage_locations_set_total_stock` | `PATCH /api/v1/storageLocations/setTotalStock` | Set total stock on storage locations |

## Supplier (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `supplier_delete` | `DELETE /api/v1/suppliers/{id}` | Delete supplier |
| `supplier_list` | `GET /api/v1/suppliers` | List suppliers |
| `supplier_update` | `PATCH /api/v1/suppliers/{id}` | Update single Supplier tags ⚠️ deprecated |
| `supplier_update_multiple` | `PATCH /api/v1/suppliers` | Update multiple suppliers tags ⚠️ deprecated |
| `supplier_view` | `GET /api/v1/suppliers/{id}` | View supplier |

## Supplier Tag (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `supplier_tag_list` | `GET /api/v1/suppliersTags` | List suppliers tags ⚠️ deprecated |

## Tag (6 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `tag_bulk_assign` | `POST /api/v2/{resource}TagAssignments` | Assign tags to multiple resources |
| `tag_bulk_remove` | `DELETE /api/v2/{resource}TagAssignments` | Remove tags from multiple resources |
| `tag_create_action` | `POST /api/v2/tags` | Create a new tag |
| `tag_delete_multiple` | `DELETE /api/v2/tags` | Delete tags |
| `tag_list` | `GET /api/v2/tags` | List tags |
| `tag_update_multiple` | `PATCH /api/v2/tags` | Update multiple tags |

## Tax (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `tax_create_v1` | `POST /api/v1/tax` | 🔒 Create tax |
| `tax_get_v1` | `GET /api/v1/tax/{id}` | 🔒 Get Tax Entry by ID |
| `tax_list_v1` | `GET /api/v1/tax` | 🔒 List Tax Entries |
| `tax_update_v1` | `PATCH /api/v1/tax/{id}` | 🔒 Update tax |

## Tax Account Mapping (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `tax_account_mapping_create_v1` | `POST /api/v1/taxAccountMapping` | 🔒 Create tax account mapping |
| `tax_account_mapping_delete_v1` | `DELETE /api/v1/taxAccountMapping/{id}` | 🔒 Delete Tax Account Mapping Entry by ID |
| `tax_account_mapping_get_v1` | `GET /api/v1/taxAccountMapping/{id}` | 🔒 Get Tax Account Mapping Entry by ID |
| `tax_account_mapping_list_v1` | `GET /api/v1/taxAccountMapping` | 🔒 List Tax Account Mapping Entries |
| `tax_account_mapping_update_v1` | `PATCH /api/v1/taxAccountMapping/{id}` | 🔒 Update tax account mapping |

## Tax Obligation (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `tax_obligation_create_v1` | `POST /api/v1/taxObligation` | 🔒 Create tax obligation |
| `tax_obligation_list_v1` | `GET /api/v1/taxObligation` | 🔒 List Tax Obligation Entries |

## Tax Rate (1 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `tax_rate_list` | `GET /api/v1/taxRates/{countryCode}` | List tax rates |

## Tax Type (5 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `tax_type_create_v1` | `POST /api/v1/taxType` | 🔒 Create tax type |
| `tax_type_delete_v1` | `DELETE /api/v1/taxType/{id}` | 🔒 Delete Tax Type Entry by ID |
| `tax_type_get_v1` | `GET /api/v1/taxType/{id}` | 🔒 Get Tax Type Entry by ID |
| `tax_type_list_v1` | `GET /api/v1/taxType` | 🔒 List Tax Type Entries |
| `tax_type_update_v1` | `PATCH /api/v1/taxType/{id}` | 🔒 Update tax type |

## Tax Type Mapping (2 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `tax_type_mapping_extended_detail_list_v1` | `GET /api/v1/taxTypeMapping/extendedDetail` | 🔒 List Tax Type Mapping Entries with Extended Detail |
| `tax_type_mapping_extended_detail_view_v1` | `GET /api/v1/taxTypeMapping/{id}/extendedDetail` | 🔒 Get Tax Type Mapping Entry with Extended Detail by ID |

## User (9 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `user_actions_download_permissions` | `GET /api/v1/users/{id}/actions/downloadPermissions` | Download user permissions |
| `user_create` | `POST /api/v1/users` | Create user |
| `user_delete` | `DELETE /api/v1/users/{id}` | Delete user |
| `user_list` | `GET /api/v1/users` | List users ⚠️ deprecated |
| `user_list_v2` | `GET /api/v2/users` | List users V2 |
| `user_permission_view` | `GET /api/v1/users/{id}/permissions` | List user permissions |
| `user_reset_password` | `POST /api/v1/users/{id}/resetPassword/request` | Request reset password email |
| `user_update` | `PATCH /api/v1/users/{id}` | Update user |
| `user_view` | `GET /api/v1/users/{id}` | View user |

## Warehouse (4 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `warehouse_create` | `POST /api/v1/warehouses` | Create warehouse |
| `warehouse_delete` | `DELETE /api/v1/warehouses/{id}` | Delete warehouse |
| `warehouse_list` | `GET /api/v1/warehouses` | List warehouses |
| `warehouse_update` | `PATCH /api/v1/warehouses/{id}` | Update warehouse |

## Webhook (6 tools)

| Tool | Endpoint | Description |
|------|----------|-------------|
| `webhook_create` | `POST /api/v1/webhooks` | Create webhook |
| `webhook_delete` | `DELETE /api/v1/webhooks/{id}` | Delete webhook |
| `webhook_event_types_list` | `GET /api/v1/webhookEventTypes` | List webhook event types |
| `webhook_list` | `GET /api/v1/webhooks` | List webhooks |
| `webhook_update` | `PATCH /api/v1/webhooks/{id}` | Update webhook |
| `webhook_view` | `GET /api/v1/webhooks/{id}` | View webhook |
