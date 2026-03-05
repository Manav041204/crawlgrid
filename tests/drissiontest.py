from DrissionPage import ChromiumPage, ChromiumOptions
import time
import threading

co = ChromiumOptions()
co.set_argument("--start-maximized")
page = ChromiumPage(co)

tab = page.latest_tab

tab.get('https://www.amazon.in/')
time.sleep(5)
ele = tab.ele('xpath://input[@id="twotabsearchtextbox"]', timeout=10)
print(ele.html)
ele.input("Tshirt")
time.sleep(5)
