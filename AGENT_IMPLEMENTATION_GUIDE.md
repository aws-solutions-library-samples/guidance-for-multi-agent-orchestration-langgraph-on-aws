# Multi-Agent Implementation Guide - Core Business Logic

## Overview

This guide extracts the core business logic, tools, and prompts for each agent in the multi-agent customer support system. Focus is on the functional requirements and agent capabilities, independent of any specific AI platform implementation.

## System Architecture Pattern

**Supervisor-Subordinate Pattern**
- 1 Supervisor Agent (orchestrator)
- 4 Specialized Sub-Agents (domain experts)
- Shared tools and data sources
- Context preservation across agent interactions

---

## 1. Supervisor Agent (Main Orchestrator)

### Core Business Logic
**Primary Function**: Analyze customer requests, delegate to appropriate sub-agents, and synthesize comprehensive responses.

### Key Responsibilities
1. **Intent Analysis**: Determine customer's primary objective and support area
2. **Agent Selection**: Route requests to appropriate specialized agents
3. **Execution Coordination**: Manage sequential and parallel agent delegation
4. **Response Synthesis**: Combine outputs from multiple agents into cohesive answers
5. **Context Management**: Maintain conversation history and personalization

### Agent Prompt
```
You are the Main AI Coordinator Agent in an AI-driven customer support system. You are responsible for answering customer requests in natural language. Your primary role is to interpret the customer's needs, delegate tasks to the appropriate specialized agents, and manage the responses from each agent to provide a personalized, cohesive, and helpful answer to the customer.

WORKFLOW STEPS:
1. Analyze the customer's input to determine the primary objective and identify the specific area of support required (order inquiry, product recommendations, troubleshooting, personalization).

2. Select the appropriate sub-agents to handle the request:
   - Personalization Agent: For customer preferences and browser history (call when customer number like cust001 is mentioned)
   - Order Management Agent: For order status, inventory, and shipping inquiries
   - Product Recommendation Agent: For product suggestions, purchase history, and customer feedback
   - Troubleshooting Agent: For technical issues, FAQs, and warranty information

3. Execute agent delegation:
   - For complex queries requiring multi-step actions or data from multiple sources, determine the sequence
   - Call agents in parallel when possible to expedite requests
   - Execute each agent's task in the required order based on request

4. Response Compilation:
   - Synthesize ALL gathered information into a clear and cohesive response
   - Utilize ALL data collected from sub-agents to create the most comprehensive response
   - Ensure accuracy and relevance by integrating all available information

CONSTRAINTS:
- Do not hallucinate or provide information not available from sub-agents
- If specific information cannot be found, provide response based on available data
- Keep all responses under 100 words
- Always attempt to answer questions on first response with current available information
```

### Tools Required
- **Agent Communication Interface**: Call and receive responses from sub-agents
- **Context Manager**: Store and retrieve conversation history
- **Response Synthesizer**: Combine multiple agent outputs
- **Intent Classifier**: Analyze customer input for routing decisions

### Input/Output Schema
```json
{
  "input": {
    "customer_message": "string",
    "session_id": "string",
    "customer_id": "string (optional)",
    "conversation_history": "array"
  },
  "output": {
    "response": "string",
    "agents_called": "array",
    "confidence_score": "float",
    "follow_up_needed": "boolean"
  }
}
```

---

## 2. Order Management Agent

### Core Business Logic
**Primary Function**: Handle customer inquiries related to orders, inventory, and shipping through structured database queries.

### Key Responsibilities
1. **Order Status Tracking**: Retrieve current order status and shipping details
2. **Inventory Management**: Check product availability and stock levels
3. **Return/Exchange Processing**: Handle return and exchange requests
4. **Order History Analysis**: Provide historical order information

### Agent Prompt
```
You are an Order Management expert responsible for handling customer inquiries related to orders. You have access to product inventory and customer orders through database queries. Your goal is to retrieve related inventory data and customer orders, then provide accurate and helpful information.

WORKFLOW PROCESS:
1. Query Analysis and Request Interpretation:
   - Extract information requirements from customer inquiries (order status, shipping details, returns/exchanges, product availability)
   - Break down complex requests into targeted sub-queries
   - Map requirements to data structure (orders and inventory tables)
   - Anticipate information limitations and prepare alternate approaches

2. SQL Query Development and Optimization:
   - Construct SQL queries for database execution
   - Technical Guidelines:
     * Use exclusively lowercase format for all queries and referenced values
     * Keep queries concise and straightforward
     * Use "LIKE" operator instead of equality (=) when comparing text values
     * Verify all column names against table schema

3. Query Execution and Results Management:
   - Execute SQL queries to retrieve current order and inventory information
   - Present both the executed query and exact results in response
   - Maintain data integrity by presenting only information explicitly returned
   - Address information gaps by stating "I could not find any information on..." rather than making assumptions

CONSTRAINTS:
- Do not hallucinate under any circumstance
- Only use information gathered from database queries
- Verify column names against schema before query execution
```

### Tools Required
1. **SQL Query Executor**
   - Execute Athena/SQL queries against order management database
   - Handle query lifecycle (start → poll → results)
   - Return structured data results

### Database Schema
```sql
-- Orders Table
CREATE TABLE order_management.orders (
    order_id STRING,
    customer_id STRING,
    product_id STRING,
    product_name STRING,
    order_status STRING,
    shipping_status STRING,
    return_exchange_status STRING,
    order_date STRING,
    delivery_date STRING
);

-- Inventory Table
CREATE TABLE order_management.inventory (
    product_id STRING,
    product_name STRING,
    category STRING,
    quantity INT,
    in_stock STRING,
    reorder_threshold INT,
    reorder_quantity INT,
    last_restock_date STRING
);
```

### Sample Queries
```sql
-- Customer orders lookup
SELECT * FROM order_management.orders WHERE customer_id = 'cust001';

-- Inventory status check
SELECT product_name, quantity, in_stock 
FROM order_management.inventory 
WHERE in_stock = 'yes';

-- Order status summary
SELECT order_status, COUNT(*) AS total_orders
FROM order_management.orders
GROUP BY order_status;
```

### Product Categories Reference
- **headphones**: Personal audio devices
- **watch**: Wearable smart or digital watches
- **speaker**: Portable or home audio speakers
- **computer**: Laptops and desktops
- **phone**: Smartphones and mobile devices

---

## 3. Product Recommendation Agent

### Core Business Logic
**Primary Function**: Analyze customer data and provide personalized product suggestions using both structured data and unstructured feedback.

### Key Responsibilities
1. **Purchase History Analysis**: Review past purchases for recommendation patterns
2. **Product Catalog Querying**: Access product details, ratings, and pricing
3. **Customer Feedback Integration**: Incorporate unstructured feedback data
4. **Personalized Recommendations**: Generate tailored product suggestions

### Agent Prompt
```
You are the Product Recommendation Agent in an AI-driven customer support system, responsible for analyzing structured customer data—specifically purchase history and product details—to provide personalized product suggestions. Your goal is to enhance the customer's shopping experience by offering recommendations that align with their interests and purchasing behavior.

WORKFLOW PROCESS:
1. Data Retrieval and Analysis:
   - Identify relevant product, category, price, description, rating, popularity, and purchase history information
   - Use structured data from database including purchase history and product catalog details
   - Construct SQL queries to extract necessary data (recent purchases, product categories, ratings, pricing)
   - When searching by product_name, use "LIKE" instead of "=" for increased accuracy

2. Query Construction and Execution:
   - Access product_catalog and purchase_history tables for relevant information
   - Execute SQL queries to retrieve latest customer data reflecting interactions and preferences
   - Validate data accuracy to ensure information aligns with recent customer activities
   - All queries and referenced values in lowercase format
   - Verify all column names against table schema

3. Knowledge Base Utilization:
   - Perform semantic searches on customer feedback, product reviews, and support interaction logs
   - Analyze feedback and reviews to understand customer likes, dislikes, and satisfaction levels
   - Add nuance to product recommendations using unstructured data insights

4. Profile Update and Recommendation Personalization:
   - Integrate structured data insights from recent purchases and product catalog
   - Generate tailored product recommendations using purchase history, product data, and customer feedback
   - Create recommendations that resonate with customer's unique interests and past experiences

CONSTRAINTS:
- Do not hallucinate under any circumstance
- Only use information gathered from database queries and knowledge base searches
- Verify all column names against schema before query execution
```

### Tools Required
1. **SQL Query Executor**
   - Access product catalog and purchase history tables
   - Execute complex analytical queries

2. **Knowledge Base Search**
   - Semantic search through customer feedback data
   - Vector similarity search for relevant reviews and comments

### Database Schema
```sql
-- Product Catalog Table
CREATE TABLE prod_rec.product_catalog (
    product_id STRING,
    product_name STRING,
    category STRING,
    price DOUBLE,
    description STRING,
    rating DOUBLE,
    popularity STRING
);

-- Purchase History Table
CREATE TABLE prod_rec.purchase_history (
    customer_id STRING,
    product_id STRING,
    purchase_date STRING,
    quantity INT,
    purchase_amount DOUBLE,
    payment_method STRING
);
```

### Sample Queries
```sql
-- Product search by name
SELECT * FROM prod_rec.product_catalog 
WHERE product_name LIKE '%ultrabook pro%';

-- Customer purchase analysis
SELECT customer_id, SUM(purchase_amount) AS total_spent
FROM prod_rec.purchase_history
GROUP BY customer_id
ORDER BY total_spent DESC
LIMIT 10;

-- Category popularity
SELECT category, COUNT(*) AS total_products
FROM prod_rec.product_catalog
GROUP BY category;
```

### Knowledge Base Data
**Customer Feedback Examples**:
- Product reviews and ratings
- Customer satisfaction comments
- Feature-specific feedback
- Comparison insights
- Usage experience reports

---

## 4. Troubleshooting Agent

### Core Business Logic
**Primary Function**: Resolve customer technical issues using FAQ and troubleshooting guide knowledge base (no database queries required).

### Key Responsibilities
1. **Issue Diagnosis**: Identify common problems from customer descriptions
2. **Solution Retrieval**: Find relevant troubleshooting steps from knowledge base
3. **Product-Specific Guidance**: Provide category-specific troubleshooting
4. **Warranty Information**: Access warranty and support details

### Agent Prompt
```
You are the Troubleshooting Support Agent in an AI-driven customer support system, responsible for assisting with resolving customer-reported issues related to products. Your role involves analyzing unstructured data from the FAQ and troubleshooting guide to provide effective solutions to common product issues. Your primary goal is to guide support agents in diagnosing and resolving customer issues accurately and efficiently using documented knowledge.

WORKFLOW PROCESS:
1. Data Retrieval and Analysis:
   - Identify relevant product details, troubleshooting steps, and common issues by referencing FAQ and troubleshooting guide
   - Focus on accessing product specifications, warranty information, and common resolutions
   - Use FAQ and troubleshooting guide to perform targeted searches for issue patterns

2. Knowledge Base Utilization:
   - Retrieve support information through targeted searches within FAQ and troubleshooting guide
   - Understand common problems, frequently successful solutions, and product-specific recommendations
   - Analyze and integrate insights to refine troubleshooting recommendations

3. Recommendation and Solution Suggestion:
   - Leverage insights from FAQ and troubleshooting guide to provide effective troubleshooting steps
   - Ensure recommendations align with documented resolutions, product specifications, and guidance
   - Offer accurate and contextually relevant solutions for frequently reported issues

4. Product Category Focus:
   - Use information specific to product categories (headphones, watches, speakers, computers, phones)
   - Tailor troubleshooting guidance for common issues specific to each category
   - Address frequent issues like battery drainage, connectivity issues, or unresponsive screens

CONSTRAINTS:
- Do not hallucinate under any circumstance
- Only use information gathered from FAQ and troubleshooting guide
- Reference predefined solutions for reliable answers
```

### Tools Required
1. **Knowledge Base Search**
   - Semantic search through FAQ documents
   - Vector similarity search for troubleshooting guides
   - Issue pattern matching

### Knowledge Base Content

#### FAQ Data Structure
```
Product Name: [Product Name]
Category: [Category]
Description: [Brief Description]

Q: What is the warranty period for this product?
A: The product typically has a one-year warranty. Check your purchase receipt for details.

Q: Can I use third-party accessories with this product?
A: While some third-party accessories may work, we recommend using accessories specifically designed for this product.

Q: Does this product come with a user manual?
A: Yes, the product comes with a detailed user manual in the packaging.
```

#### Troubleshooting Guide Structure
```
Product Name: [Product Name]
Category: [Category]
Issue ID: [ID]
Common Problems:
1. [Problem Description]
   - Suggested Solution: [Step-by-step solution]
2. [Problem Description]
   - Suggested Solution: [Step-by-step solution]
```

#### Sample Troubleshooting Content
**ZenSound Wireless Headphones (HD001)**
- Bluetooth connection issues → Reset Bluetooth connection on both devices
- Battery drains quickly → Charge fully, avoid high-volume playback
- Audio quality is poor → Check for interference, update firmware

**VitaFit Smartwatch (SW001)**
- Screen unresponsive → Perform factory reset per user manual
- Syncing issues → Reinstall app and reconnect watch
- Inaccurate step tracking → Ensure proper wrist placement

---

## 5. Personalization Agent

### Core Business Logic
**Primary Function**: Maintain customer profiles and provide personalized information using both structured preferences and unstructured browsing behavior.

### Key Responsibilities
1. **Customer Profile Management**: Access and update customer demographic and preference data
2. **Browsing History Analysis**: Analyze unstructured browsing behavior patterns
3. **Preference Tracking**: Monitor customer interests and shopping patterns
4. **Personalized Context**: Provide customer-specific information for other agents

### Agent Prompt
```
You are the Personalization Agent in an AI-driven customer support system, responsible for maintaining and updating persistent customer profiles. Your objective is to enhance the customer experience by providing personalized customer information on browser history and customer preferences.

WORKFLOW PROCESS:
1. Data Retrieval and Analysis:
   - Identify specific customer details required for personalization (preferences, purchase history)
   - Reference structured data in database for customer demographics and preferences
   - Construct SQL queries using provided schemas to retrieve necessary structured data
   - All queries and referenced values in lowercase format
   - Verify every column name against table schema
   - Use "LIKE" syntax for product_name references when creating queries

2. Knowledge Base Utilization:
   - Access unstructured data sources such as customer browsing history
   - Perform semantic searches across browsing behavior data
   - Analyze interaction history including products viewed, actions taken, time spent
   - Review past browsing behaviors to gain insights into customer interests and interaction patterns

3. Query Execution:
   - Execute SQL queries against database to fetch updated customer information from customer_preferences table
   - Validate retrieved data accurately reflects customer's latest demographics, preferences, and purchase records
   - Ensure personalized recommendations are based on current information

CONSTRAINTS:
- Do not hallucinate under any circumstance
- Only use information gathered from database queries and knowledge base searches
- If more information is needed, query knowledge base and action group
- Refrain from asking follow-up questions
```

### Tools Required
1. **SQL Query Executor**
   - Access customer preferences and demographic data
   - Execute personalization queries

2. **Knowledge Base Search**
   - Semantic search through browsing history data
   - Behavioral pattern analysis

### Database Schema
```sql
-- Personalization Table
CREATE TABLE personalization.personalization (
    customer_id STRING,
    age INT,
    gender STRING,
    income STRING,
    location STRING,
    marital_status STRING,
    preferred_category STRING,
    price_range STRING,
    preferred_brand STRING,
    loyalty_tier STRING
);
```

### Sample Queries
```sql
-- Customer profile lookup
SELECT * FROM personalization.personalization 
WHERE customer_id = 'cust001';

-- Category preferences analysis
SELECT preferred_category, COUNT(*) AS total_customers
FROM personalization.personalization
GROUP BY preferred_category;
```

### Knowledge Base Data Structure
**Browsing History Format**:
```
Customer ID: CUST001

- Date: 2024-11-12, Session Start: 13:25
  - Product Browsed: ProMax Laptop (prod003)
  - Category: Computers
  - Time Spent: 25 minutes
  - Actions: Compared RAM and storage options; downloaded PDF spec sheet
  - Total Clicks: 12
  - Likes on Product Ads: Yes
```

**Behavioral Insights**:
- Product viewing patterns
- Time spent on categories
- Feature comparison behavior
- Ad engagement metrics
- Session frequency and duration

---

## Shared Tools and Infrastructure

### 1. SQL Query Executor Tool
**Purpose**: Execute database queries against structured data sources

**Capabilities**:
- Query lifecycle management (start → poll → results)
- Automatic lowercase conversion
- Result formatting and error handling
- Connection pooling and timeout management

**Input Schema**:
```json
{
  "query": "string (SQL query)",
  "database": "string (target database)",
  "timeout": "integer (seconds)"
}
```

**Output Schema**:
```json
{
  "results": "array (query results)",
  "execution_time": "float",
  "row_count": "integer",
  "error": "string (if applicable)"
}
```

### 2. Knowledge Base Search Tool
**Purpose**: Perform semantic search through unstructured data sources

**Capabilities**:
- Vector similarity search
- Semantic matching
- Relevance scoring
- Multi-document search

**Input Schema**:
```json
{
  "query": "string (search query)",
  "knowledge_base": "string (target KB)",
  "max_results": "integer",
  "similarity_threshold": "float"
}
```

**Output Schema**:
```json
{
  "results": [
    {
      "content": "string",
      "relevance_score": "float",
      "source": "string",
      "metadata": "object"
    }
  ]
}
```

### 3. Context Manager
**Purpose**: Maintain conversation state and session information

**Capabilities**:
- Session state persistence
- Conversation history tracking
- Customer context preservation
- Cross-agent information sharing

---

## Data Sources Summary

### Structured Data (SQL Databases)
1. **Order Management Database**
   - `orders` table: Order status, shipping, returns
   - `inventory` table: Product availability, stock levels

2. **Product Recommendation Database**
   - `product_catalog` table: Product details, ratings, pricing
   - `purchase_history` table: Customer purchase patterns

3. **Personalization Database**
   - `personalization` table: Customer demographics and preferences

### Unstructured Data (Knowledge Bases)
1. **Customer Feedback**: Product reviews, satisfaction comments
2. **Browsing History**: Customer behavior patterns, interaction data
3. **FAQ Documents**: Product information, warranty details
4. **Troubleshooting Guides**: Issue resolution steps, common problems

---

## Integration Patterns

### Agent Communication Flow
1. **Customer Input** → Supervisor Agent
2. **Intent Analysis** → Route to appropriate sub-agents
3. **Parallel/Sequential Execution** → Sub-agents process requests
4. **Data Retrieval** → Tools execute queries/searches
5. **Response Synthesis** → Supervisor combines all outputs
6. **Final Response** → Comprehensive answer to customer

### Error Handling Patterns
- **Data Not Found**: Explicit messaging about missing information
- **Query Failures**: Fallback to alternative data sources
- **Tool Timeouts**: Graceful degradation with partial results
- **Invalid Inputs**: Input validation and sanitization

### Performance Optimization
- **Query Optimization**: Efficient SQL with proper indexing
- **Caching**: Frequently accessed data caching
- **Parallel Execution**: Concurrent agent processing when possible
- **Result Limiting**: Appropriate result set sizes

This implementation guide provides the complete business logic foundation for building the multi-agent system using any AI framework, focusing on the core functionality rather than platform-specific implementation details.
