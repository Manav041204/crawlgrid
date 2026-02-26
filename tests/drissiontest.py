from DrissionPage import ChromiumPage, ChromiumOptions
import time
import threading

co = ChromiumOptions()
page = ChromiumPage(co)

tab = page.latest_tab

tab.get('https://github.com/Manav041204/crawlgrid')
an_ele = tab.ele('xpath:(//ol[@class="prc-Breadcrumbs-BreadcrumbsList-BKjpe"]//li/a)[1]')
an_ele.click()
print(an_ele.html)
