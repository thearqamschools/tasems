# Books ordering on the website — prompt for Claude

Copy everything below the line and give it to Claude in the website's project.

---

## Task

Add a **Books** feature to the website of **The Arqam Schools**. The website and its admin panel already exist and are running. Customers order books through a page on the website, and the office handles the orders in the website's **admin panel**.

Today, books are sold through a separate online system. This feature replaces it.

**Before you write any code:**
1. Look at the website's code: its framework, database, admin panel, hosting and how it is deployed.
2. Write me a short plan covering the pages, the database tables, and where the feature fits in the admin panel.
3. List anything below that does not fit the existing website.

Wait for my approval of the plan. Build and test it on a test copy first, not on the live website. **Do not deploy to the live website, and do not buy or sign up for any service, without my explicit approval.**

## Who uses it

- **Customers** order books. A customer can be one of our branches, a book shop, or anyone else; we treat them all the same.
- A customer is identified by their **mobile number**, which is the main key. We also keep their **name** and **address**.
- The **office** handles orders in the admin panel: checking, packing, delivering, recording payments, returns and stock.
- Books are a **separate system** from anything else on the website or in our school software, with their own stock and their own accounts.

## 1. Book inventory (admin panel)

For each book, record:
- **class** (e.g. Play Group, Nursery, Prep, Class 1 … Matric)
- **book name**
- **stock in hand**
- **purchase price**
- **sale price**
- whether the book is shown to customers (active / hidden)

The office should be able to:
- add, edit and hide books
- add stock (purchases received), with the date and a note
- see a full stock history for each book

Do not invent book names, prices or classes. The office enters them. Demo data may be used on the test copy only, and must be clearly marked as demo data.

## 2. Customer order page (public website)

1. The website gets a **"Books"** button that leads to the order page.
2. The customer types their **mobile number**. There is no password.
   - If the number is new, they also type their **name** and **address**.
   - If the number is known, their name and address are filled in, and they can correct them.
3. An **order form** shows **every active book in stock, grouped by class**. Each row shows:
   - class
   - book name
   - **sale price**
   - a **quantity** box
   - the **line total** (price × quantity), which updates while they type
4. The **order total** shows at the bottom and stays visible while they scroll.
5. **View / Preview** shows a summary of only the books they chose, with quantities, line totals and the total. From there they can go back and change the order.
6. They choose **Pick up** (they collect it themselves) or **Delivery**.
7. **Place order.** They then see the order number and a short thank-you message.

### Order history and editing

- After typing their mobile number, the customer sees their **order history**. Each order shows its number, date, total and status.
- An order that is **not yet paid** can be **edited** by the customer: change quantities, or add and remove books.
- **Every edit is kept on record**, showing what changed and when. The admin panel shows that the order was edited.
- Once any payment is recorded, the customer can no longer edit the order.

### Things the customer never sees

- purchase prices
- discounts
- other customers' data

Keep the page simple, mobile-first (most customers use phones), fast, and easy to read.

## 3. Orders in the admin panel

- A list of orders showing:
  - order number
  - date
  - customer name and mobile number
  - pick up / delivery
  - total, discount, amount paid, balance
  - status
- Filters by status and date, and a search by mobile number, name or order number.
- **Statuses:** New → Checked → Packed → Delivered / Collected, plus Cancelled.
- **Payment status** is shown separately: **Pending / Part paid / Paid**.
- The order page shows:
  - the customer
  - the books
  - the edit history
  - the payments
  - the returns
- The office can also place an order on a customer's behalf, for example when the customer calls.

## 4. Invoice with order ID and barcode

- Every order has a unique **order ID**, printed on the invoice as a **barcode**.
- The invoice is printable and can be downloaded as a PDF. It shows:
  - The Arqam Schools name and logo
  - the order ID and barcode
  - the date
  - the customer's name, mobile number and address
  - pick up / delivery
  - the books (class, book, quantity, price, line total)
  - the total, discount, paid amount and **balance**
- Contact details on the invoice must be exactly these:
  - The Arqam Schools, Sanora Colony, Samanabad, Faisalabad, Pakistan
  - Phone: 041-2660265, 041-2406479
  - WhatsApp: 0339-2406479
  - www.thearqam.com

## 5. Recording a payment (admin panel)

1. **Scan the barcode** or type the order ID. The order opens, showing its total, what has been paid and the balance.
2. Enter:
   - **amount received**. Part payments are allowed, and an order can have several payments.
   - **method**: cash or bank transfer
   - **account**: which cash account or **which bank account** it went into. The list of accounts is managed in the admin panel.
   - **received by**: the admin user who is logged in, filled in automatically and not editable
   - **date**
   - **receipt**: attach a photo or PDF of the receipt (optional for cash)
   - **note**
   - **discount** (optional): typed by hand by the office, as an amount. It reduces the balance and is never shown to the customer. Record who gave it.
3. Save. The payment is recorded against the order and the payment status updates.

There are **no delivery charges**.

## 6. Stock rules

- **Stock is taken off when the payment is recorded**, not when the order is placed.
  - *To confirm with me before building:* with part payments, is stock taken off at the **first** payment or only when the order is **fully paid**? Ask me. Until I answer, design so that either works.
- The order form shows only books with stock. A customer cannot order more than the stock in hand. Check this again when the order is placed and when the payment is recorded.
- Stock never goes below zero. Every stock change (purchase, sale, return, correction) is kept in the stock history with the user and the date.

## 7. Returns, including part returns

A customer may return some or all of what they took (e.g. 2 of 10 books). Proposal (confirm with me before building):
- The office makes a **Return note** against the order. They pick the order and type how many of each book come back; this cannot be more than was taken and not already returned.
- The returned books go **back into stock**.
- The amount (at the price charged) is either **paid back** (method, account, by whom, date, note) or **kept as credit** for that customer's next order.
- The order shows what was returned, and the return note can be printed.

## 8. Reports (admin panel)

Every report can be printed and downloaded as PDF and Excel:
- **Stock:** each book with its class, stock in hand, purchase price, sale price, stock value at purchase price and at sale price
- **Sales:** by date range, by book and class, by customer
- **Payments received:** by date, method, account, and the user who received them
- **Unpaid and part-paid orders**, with balances
- **Discounts given**, with who gave them
- **Returns**
- **Profit:** sale value minus purchase value of the books sold, minus discounts

## 9. Safety and privacy

There is no password, so anyone who knows a mobile number could see that customer's orders:
- In the order history, show only the order number, date, books, total and status. Show the address only partly. Never show payment details or receipts.
- Limit how often the order page can be used from one device or network (rate limiting), and block automated abuse.
- Validate Pakistani mobile numbers (e.g. 03xx-xxxxxxx) and store them in one format.
- Every order is checked by the office before it is packed, so a false order does no harm.
- Do not add paid SMS or WhatsApp codes now. You may suggest them as a later option.
- The admin side needs a login, and only admin users with the Books permission can use it.
- Receipts and attachments are visible in the admin panel only.

## 10. General rules

- Use the official name **The Arqam Schools** exactly as written.
- Do not invent prices, book names, figures, policies or contact numbers.
- Wording is clear, polite and simple. Add an **Urdu** version if the website already supports Urdu.
- Write tests for the money and stock rules (totals, part payments, discounts, balances, stock taken off on payment, returns, edits blocked after payment).
- Show me screenshots of the customer pages (on a phone-sized screen) and the admin pages, and a printed invoice, before asking me to approve.
- Explain every step to me in simple Roman Urdu.
