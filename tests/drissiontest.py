from DrissionPage import ChromiumPage, ChromiumOptions
import time
import threading

co = ChromiumOptions()
page = ChromiumPage(co)

tab_man = {}
for i in range(5):
    tab = page.new_tab()
    tab_man[tab.tab_id] = tab


threads = []

for i in range(5):
    thread = threading.Thread(target=lambda t: t.get("https://google.com"), args=(tab_man[list(tab_man.keys())[i]],))
    thread.start()
    threads.append(thread)

for thread in threads:
    thread.join()

tab_man[list(tab_man.keys())[0]].ele('xpath://button[@aria-haspopup="menu"]').click()