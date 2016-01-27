from __future__ import print_function
import os
import mechanize
import BeautifulSoup
from requests.compat import urljoin
import pdfkit
import sqlite3 as sql
import re
import time
import datetime
import click

import unittest


def get_browser():
    """
    creates and returns an instance of the mechanize browser
    """
    browser = mechanize.Browser()
    browser.set_handle_robots(False)
    browser.addheaders = [("User-agent", "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.13) Gecko/20101206 Ubuntu/10.10 (maverick) Firefox/3.6.13")]
    return browser


def sign_in(browser, credentials):
    """
    Sign in with instance of mechanize browser. Authentication information is passed through the `credentials` object
    """
    sign_in = browser.open("http://www.amazon.com/gp/flex/sign-out.html")
    browser.select_form(name="signIn")
    browser["email"] = credentials["username"]
    browser["password"] = credentials["password"]
    sign_in_status = browser.submit()
    sign_in_status_msg = sign_in_status.read()
    error_msgs = [
        "Missing e-mail or mobile phone number. Please correct and try again"
    ]
    sign_in_failed = False
    for err_msg in error_msgs:
        sign_in_failed = err_msg in sign_in_status_msg
        if sign_in_failed:
            break
    return browser, sign_in_failed


def get_html(browser, url):
    """
    Downloads webpage from given url with the help of the passed browser  instance and returns a BeautifulSoup object off of that html. Browser instance is responsible for maintaining session state.
    """
    raw_html = browser.open(url)
    html = BeautifulSoup.BeautifulSoup(raw_html.read())
    return browser, html


def get_recent_orders(browser):
    """
    Returns the default orders page, last 6 months' order details landing page
    """
    recent_orders_page = "https://www.amazon.com/gp/css/order-history/ref=nav_youraccount_orders"
    return get_html(browser, recent_orders_page)


def get_recent_orders_dummy(browser, orders_page=""):
    """
    For debug purpose, it reads an instance of default orders page from a static html file and returns a BeautifulSoup object off that.
    """
    with open("./aux/out.html", "r") as mfile:
        html = BeautifulSoup.BeautifulSoup(mfile.read())
    return browser, html


def get_specific_order_page(browser, src, dst, indx):
    """
    Returns specific order history page html while handling pagination.
    abs(dst - src) == 1
    indx = 10 * src
    if dst < src: indx = 10 * (dst - 1)
    """
    base = "https://www.amazon.com/gp/your-account/order-history"
    params = "/ref=oh_aui_pagination_{_from}_{_to}?ie=UTF8&orderFilter=months-6&search=&startIndex={_start}".format(_from=src, _to=dst, _start=indx)
    # order_page_url = urljoin(base, params)
    order_page_url = base + params
    return get_html(browser, order_page_url)


def find_order_count(html):
    """
    Accepts BeautifulSoup html DOM object, finds and returns total number of orders
    """
    reg = re.compile(r'[^\d]*(\d{1,})[\s]*order', re.IGNORECASE)
    total = html.find('span', text=reg, attrs={'class': 'num-orders'}).__str__()
    n = re.match(reg, total)
    if n:
        return int(n.group(1))
    return 0


def get_existing_orders():
    """
    Returns a list of the order numbers from database for already processed orders
    """
    conn = get_database_connection('AmazonInvoices.db')
    cur = conn.cursor()
    cur.execute("SELECT ID FROM AMAZON WHERE DONE=1;")
    existing = {str(order_id[0]): True for order_id in list(cur.fetchall())}
    conn.close()
    return existing


def extract_unix_time(html):
    months = {}
    order_date_str = html.find('span', text=re.compile(r'[\s]*Order placed[\s]*'), attrs={'class': 'a-color-secondary label'}).parent.parent.parent.find('span', attrs={'class': 'a-color-secondary value'}).text.strip()
    # order_date_str = """January 7, 2016"""
    try:
        order_date = datetime.datetime.strptime(order_date_str, '%B %d, %Y')
        return order_date
    except ValueError as e:
        # if "does not match format" in str(e):
        #     reg = re.compile(r'[\s]*([A-z]+)[\s]*([0-9]+)[,\s]+([0-9]{4})')
        #     dt = re.match(reg, order_date_str)
        #     m = dt.group(1)
        #     d = dt.group(2)
        #     y = dt.group(3)
        #     order_date = datetime.datetime(y, m, d)
        raise e
    return None


def not_in_timeframe(order_date, tf):
    return order_date > tf["start"] or order_date < tf["end"]


def extract_orders(html, timeframe):
    """
    Extracts all order details from the passed html page and returns a list of the newly found order objects
    """
    orders = []
    base = "https://www.amazon.com"

    for item in html.findAll("div", {"class": "a-box-group a-spacing-base order"}):
        order_date = extract_unix_time(item)
        if (order_date is None) or not_in_timeframe(order_date, timeframe):
            continue
        order_no = item.find("div", {"class": "a-fixed-right-grid-col actions a-col-right"}).find("span", {"class": "a-color-secondary value"})
        invoice_link = item.find('a', text="Invoice", attrs={'class': 'a-link-normal'}, href=True).parent["href"]
        link = urljoin(base, invoice_link)
        orders.append({
            "id": str(order_no.text),
            "url": str(link),
            "date": str(order_date),
            "done": 0
        })
    return orders


def remove_duplicates(fresh, existing):
    """
    Checks the order ids from existing orders and returns only new ones
    from fresh after removing the duplicates
    """
    return list([order for order in fresh if order.get("id") and not existing.get(order.get("id"), None)])


def get_new_orders(order_count, html, timeframe, existing_orders, browser):
    """
    Handles pagination in order details page. Replicates ideal urls
    for different page navigation and fetches all new orders
    (the ones that haven't been processed already)
    """
    # order_count = 10  # don't forget to remove this line
    new_orders = []
    fresh_orders = extract_orders(html, timeframe)
    new_orders.extend(remove_duplicates(fresh_orders, existing_orders))

    for page, start_index in enumerate(range(10, order_count, 10)):
        browser, html = get_specific_order_page(browser, page+1, page+2, start_index)
        # with open("page{}_{}.html".format(page+1, page+2), "wb") as filez:
        #     filez.write(html.prettify())
        fresh_orders = extract_orders(html, timeframe)
        new_orders.extend(remove_duplicates(fresh_orders, existing_orders))
    return browser, new_orders


def print_pdf(order, browser):
    """
    Fetches invoice url from order object and prints out the invoice
    """
    order_id = order["id"]
    save_location = "./static/assets/pdf/"
    if not os.path.exists(save_location):
        os.makedirs(save_location)
    pdf_file = 'invoice_' + str(order_id) + '.pdf'
    filename = os.path.join(save_location, pdf_file)
    url = order["url"]
    browser, html = get_html(browser, url)
    try:
        # pdfkit.from_url(url, filename)
        # pdfkit.from_file('test.html', pdf_file)
        pdfkit.from_string(html.prettify(), filename, options={'quiet': ''})
        order["pdf"] = filename
    except Exception as ex:
        raise ex
    return True


def generate_new_invoices(orders, browser):
    """
    Generates invoices for all the orders and marks the successful ones as done
    """
    for order in orders:
        if print_pdf(order, browser):
            order["done"] = 1
    return orders


def get_database_connection(dbname):
    """
    Connects to sqlite database and returns a connection instance
    """
    db_location = "./static/assets/db/"
    if not os.path.exists(db_location):
        os.makedirs(db_location)
    db = os.path.join(db_location, dbname)
    conn = sql.connect(db)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE  IF NOT EXISTS AMAZON (
                ID TEXT PRIMARY KEY NOT NULL,
                URL TEXT NOT NULL,
                PDF TEXT NOT NULL,
                DONE INT DEFAULT 0);""")
    conn.commit()
    return conn


def save_new_orders(orders):
    """
    All the new orders are saved. The ones that already exists are updated
    """
    conn = get_database_connection('AmazonInvoices.db')
    cur = conn.cursor()
    saved = 0
    for order in orders:
        _id = order.get("id", None)
        _url = order.get("url")
        _pdf = order.get("pdf", None)
        _done = order.get("done", 0)
        if not (_id and _url and _pdf):
            continue
        params = (_id, _url, _pdf, _done)
        cur.execute("INSERT OR REPLACE INTO AMAZON (ID, URL, PDF, DONE) VALUES (?, ?, ?, ?);", params)
        conn.commit()
        saved += 1
    conn.close()
    return saved


def generate(auth, timeframe):
    """
    main controller
    """
    # print("Auth:", auth, "Time range:", timeframe)
    # print(timeframe["start"] - timeframe["end"])
    return {
        "success": True,
        "added": 0,
        "description": "Working as expected"
    }
    browser = get_browser()
    browser, sign_in_failed = sign_in(browser, auth)
    if sign_in_failed:
        return {
            "success": False,
            "added": 0,
            "description": "Sign in failed"
        }
    browser, html = get_recent_orders(browser)
    order_count = find_order_count(html)
    if not order_count:
        return {
            "success": True,
            "added": 0,
            "description": "No new order found"
        }
    existing_orders = get_existing_orders()
    browser, new_orders = get_new_orders(order_count, html, timeframe, existing_orders, browser)
    new_orders = generate_new_invoices(new_orders, browser)
    saved = save_new_orders(new_orders)
    return {
        "success": True,
        "added": saved,
        "description": "New invoices added successfully"
    }


@click.command()
@click.option('--username', '-u', prompt='Amazon username', help='Amazon account username you want to use')
@click.option('--password', '-p', prompt='Amazon password', confirmation_prompt=True, hide_input=True, help='Password of the amazon account you are using')
@click.option('--start', '-s', help='Start date of date range (m/d/yyyy)')
@click.option('--end', '-e', help='End date of date range (m/d/yyyy)')
def cli(username, password, start, end):
    auth = {"username": username, "password": password}
    if not bool(start):
        start = datetime.datetime.now()
    else:
        m, d, y = (int(i) for i in re.split('\.|\/|-', start))
        start = datetime.datetime(y, m, d)
    if not bool(end):
        end = datetime.datetime.now() - datetime.timedelta(days=180)
    else:
        m, d, y = (int(i) for i in re.split('\.|\/|-', end))
        end = datetime.datetime(y, m, d)
    timeframe = {"start": start, "end": end}
    if(start < end):
        timeframe = {"start": end, "end": start}
    click.echo(str(generate(auth, timeframe)))


class TestAmazon(unittest.TestCase):

    def setUp(self):
        self.br = mechanize.Browser()
        self.br.set_handle_robots(False)
        self.br.addheaders = [("User-agent", "Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.9.2.13) Gecko/20101206 Ubuntu/10.10 (maverick) Firefox/3.6.13")]

    def test_get_html(self):
        url = "http://www.example.com"
        self.br, html = get_html(self.br, url)
        h1 = html.find("h1")
        self.assertEqual(h1.text, "Example Domain")

    def test_something(self):
        self.br, html = get_recent_orders_dummy(self.br)

    def test_remove_duplicates(self):
        existing = {"123": True, "234": True, "345": True, "456": True}
        fresh = [{"id": "012", "val": 120},
                 {"id": "123", "val": 123},
                 {"id": "456", "val": 456},
                 {"id": "789", "val": 789},
                 {"id": "890", "val": 890}]

        ideal = [{"id": "012", "val": 120},
                 {"id": "789", "val": 789},
                 {"id": "890", "val": 890}]

        new = remove_duplicates(fresh, existing)

        self.assertEqual(new, ideal)
        self.assertTrue(len(fresh) >= len(new))
        for n in new:
            self.assertFalse(n["id"] in existing)
            self.assertTrue(n in fresh)

    def TearDown(self):
        self.br = None

if __name__ == '__main__':
    # unittest.main()
    cli()
