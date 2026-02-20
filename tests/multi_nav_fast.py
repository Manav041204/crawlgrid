from DrissionPage import ChromiumPage

browser = ChromiumPage()
tab_pool = []    
tab_in_use_pool = []

def tab_creator():
    for _ in range(5):
        tab = browser.new_tab()
        tab_pool.append(tab)


async def tab_handler():
    while True:
        if tab_pool:
            tab = tab_pool.pop()
            tab_in_use_pool.append(tab)
        else:
            await asyncio.sleep(1)


async def process_url(tab):
    tab.get()

