# Xentral MCP Tool Definitions

This document defines all available MCP tools for Xentral ERP integration.

## Sales & CRM (26 tools)

- **`search_customers`** - Search and find customers by various criteria
  - Parameter: `customer_id`, `customer_number` (optional), `name`, `email`, `phone`, `city` OR
  - **Xentral MCP Status:** ✅ Implemented
  
- **`get_order_overview`** - Display complete order summary with key information
  - Parameter: `order_id`, `order_number` (required), `external_order_number`, `customer_order_number`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`get_customer_history`** - Display customer purchase and interaction history
  - Parameter: `customer_id`, `customer_number` (required), `limit`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`track_order_progress`** - Track detailed progress of order processing
  - Parameter: `order_id`, `order_number` (required), `customer_id`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`quick_quote`** - Create quick quotation for customer
  - Parameter: `customer_id` (required), `product_id`, `quantity`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`create_customer`** - Create new customer with contact information
  - Parameter: `name` (required), `email`, `phone`, `street`, `city`, `zip`, `country`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Logistics & Fulfillment (20 tools)

- **`check_product_availability`** - Check current stock availability
  - Parameter: `product_id`, `product_number` (required), `warehouse_id`, `quantity`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`check_stock_location`** - Check product location in warehouse
  - Parameter: `product_id`, `product_number` (required), `warehouse_id`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`process_return`** - Process product return and refund
  - Parameter: `order_id`, `order_number` (required), `reason`, `restocking_fee`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`create_shipment_quick`** - Create shipment quickly
  - Parameter: `order_id` (required), `carrier`, `tracking_number`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Service & Support (12 tools)

- **`create_ticket_from_call`** - Create support ticket from customer call
  - Parameter: `customer_id`, `customer_number` (required), `description`, `priority`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`search_tickets`** - Search support tickets
  - Parameter: `customer_id`, `status`, `priority`, `page`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Purchasing & Procurement (14 tools)

- **`get_purchase_requests`** - Retrieve pending purchase requests
  - Parameter: `page`, `limit`, `status`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`create_purchase_order_fast`** - Create purchase order quickly
  - Parameter: `supplier_id` (required), `product_id`, `quantity`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Accounting & Finance (14 tools)

- **`get_overdue_invoices`** - Get list of overdue invoices
  - Parameter: `days_overdue`, `page`, `limit`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`quick_journal_entry`** - Create quick journal entry
  - Parameter: `description` (required), `amount`, `account`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Administration & Master Data (8 tools)

- **`create_product`** - Create new product
  - Parameter: `name` (required), `number` (required), `description`, `ean`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`update_product_price`** - Update product pricing
  - Parameter: `product_id` (required), `sales_price`, `purchase_price`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Communication & Workflow (15 tools)

- **`send_customer_update`** - Send update notification to customer
  - Parameter: `customer_id` (required), `message`, `method`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`upload_document`** - Upload document to system
  - Parameter: `document_path` (required), `document_type`, `related_entity`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Analytics & Reporting (20 tools)

- **`get_daily_sales`** - Get daily sales metrics
  - Parameter: `date`, `date_from`, `date_to`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`get_open_orders`** - Get count of open orders
  - Parameter: `page`, `limit`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`get_stock_alerts`** - Get low stock alerts
  - Parameter: `warehouse_id`, `threshold`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

## Mobile & Integration (8 tools)

- **`sync_bank_data`** - Synchronize bank data
  - Parameter: `bank_account_id`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

- **`update_web_shop`** - Update web shop data
  - Parameter: `product_id`, `field`, `value`
  - **Xentral MCP Status:** ❌ Not implemented (skeleton)

---

## Tool Status Summary

- ✅ Implemented: search_customers
- 🚧 Skeleton (Planned): All other tools

To implement a tool:
1. Create file `xentral/{tool_name}.py`
2. Implement class inheriting from `XentralAPIBase`
3. Implement `execute(arguments: Dict[str, Any]) -> str` method
4. Restart server (tools auto-discovered)
