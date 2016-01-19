<center><h1>Amazon Invoice Automation</h1></center>
<hr>

## Log into Amazon

Log into Amazon using the following base snippet. Store data in session which you can use for future queries. Check response content to determine if its a successful login.

``` Python
#!/usr/bin/env python3
import requests

session = requests.Session()
data = {'email':'sudipta.genius@gmail.com', 'password':'password'}
header={'User-Agent' : 'Mozilla/5.0'}

response = session.post('https://www.amazon.com/gp/sign-in.html', data, headers=header)
return response.content
```

## Scrape Order Details Page for Order Numbers

### Go to page
After successful login, go to order details page
`https://www.amazon.com/gp/css/order-history`.

> By default it will load order details for last 6 months which is sufficient for monthly automated invoice preparation. If required more, you can change some query parameters easily to suit your needs.

### Count number of orders

### Scrape Invoice links
Next find out all anchor tags with `Invoice` text inside them as well as a link that points to `https://www.amazon.com/gp/css/summary/print.html/ref=oh_aui_pi_o00_?orderID=123-1234567-1234567`, where order number is given by `123-1234567-1234567`. In the link, base url (`//www.amazon.com`) might be omitted; so look for `/gp/css/summary/print.html/ref=oh_aui_pi_o00_`.

One sample link looks like: `<a class="a-link-normal" href="/gp/css/summary/print.html/ref=oh_aui_pi_o00_?ie=UTF8&amp;orderID=123-1234567-1234567">Invoice</a>`

### Look into multiple pages
Number of orders might be more than 10 and hence we need to deal with pagination issues.

This is the url when I click page 2: `https://www.amazon.com/gp/your-account/order-history/ref=oh_aui_pagination_1_2?ie=UTF8&orderFilter=months-6&search=&startIndex=10`

This is the url for page 3: `https://www.amazon.com/gp/your-account/order-history/ref=oh_aui_pagination_2_3?ie=UTF8&orderFilter=months-6&search=&startIndex=20`

Explicit click to page 1: `https://www.amazon.com/gp/your-account/order-history/ref=oh_aui_pagination_3_1?ie=UTF8&orderFilter=months-6&search=&startIndex=0`

Clicking on `next` from page 1 to 2: `https://www.amazon.com/gp/your-account/order-history/ref=oh_aui_pagination_1_2?ie=UTF8&orderFilter=months-6&search=&startIndex=10`

Clicking on `next` from page 2 to 3: `https://www.amazon.com/gp/your-account/order-history/ref=oh_aui_pagination_2_3?ie=UTF8&orderFilter=months-6&search=&startIndex=20`

Clicking on `previous` from page 3 to 2: `https://www.amazon.com/gp/your-account/order-history/ref=oh_aui_pagination_3_2?ie=UTF8&orderFilter=months-6&search=&startIndex=10`

Clicking on `previous` from page 2 to 1: `https://www.amazon.com/gp/your-account/order-history/ref=oh_aui_pagination_2_1?ie=UTF8&orderFilter=months-6&search=&startIndex=0`

Scrape invoices (order numbers and corresponding links) till you hit the total invoice number found on first `order history` page all while discarding duplicate entries.

## Go to order invoice page
Next, using the already stored `requests.Session` go to the invoice urls one by one. Sample url: `https://www.amazon.com/gp/css/summary/print.html/ref=oh_aui_pi_o00_?orderID=123-1234567-1234567`

```python
invoice_url = 'https://www.amazon.com/gp/css/summary/print.html/ref=oh_aui_pi_o00_?orderID=123-1234567-1234567'
response = session.post(invoice_url, data, headers=header)

return response.content
```

## Print the Invoices

You already have the response content or, the html content returned by amazon for that particular order number. Simply use that with the help of `pdfkit` to save file as a pdf with possibly the order number as part of filename.

``` python
import pdfkit

order_id = '123-1234567-1234567'
pdf_file = 'invoice_' + str(order_id) + '.pdf'
html_content = response.content

# pdfkit.from_url('http://amazon.com/...', pdf_file)
# pdfkit.from_file('test.html', pdf_file)
pdfkit.from_string(html_content, pdf_file)
```
