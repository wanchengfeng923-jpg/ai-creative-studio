"""独立启动网络代理工作台。"""

import tkinter as tk

from launcher import ProxyWorkbench


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    window = ProxyWorkbench(root)
    window.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
