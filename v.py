import os
import asyncio
from datetime import datetime
from typing import List, Optional, Tuple, Set
from rich.progress import Progress, BarColumn, TextColumn, DownloadColumn, TransferSpeedColumn, TimeRemainingColumn

# ========= CONFIG =========
API_ID = 666 # Change to your API ID
API_HASH = "YOUR_API_HASH_HERE" # Change to your API Hash
SESSION_NAME = "tg_session"
# ==========================
today = datetime.today().strftime("%d-%m-%Y")
current_dir = os.getcwd()
OUTPUT_DIR = os.path.join(current_dir, "result", today)
# ==========================

# ========= OPTION =========
BATCH_SIZE = 50      # how many items per page
SINCE_DATE = None    # "YYYY-MM-DD" to filter messages, or None for no filter
HIDE_BOT_DM = True   # hide direct messages with bots
# ==========================

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.tl.types import (
    Channel, Chat, User, InputPeerChannel,
    Message, MessageMediaDocument, MessageMediaPhoto
)

try:
    import curses
except Exception:
    print("Curses module not available. Please run this script in a terminal that supports curses.")
    raise

def ensure_dir(p): os.makedirs(p, exist_ok=True)

def human_size(n: Optional[int]) -> str:
    if not n or n <= 0:
        return "-"
    units = ["B","KB","MB","GB","TB"]
    i = 0
    f = float(n)
    while f >= 1024 and i < len(units)-1:
        f /= 1024.0
        i += 1
    return f"{f:.1f} {units[i]}"

def label_of_entity(ent) -> Tuple[str, str]:
    if isinstance(ent, Channel):
        kind = "channel" if getattr(ent, "megagroup", False) is False else "supergroup"
        title = getattr(ent, "title", "") or ""
    elif isinstance(ent, Chat):
        kind = "group"
        title = getattr(ent, "title", "") or ""
    elif isinstance(ent, User):
        kind = "bot" if ent.bot else "user"
        title = (ent.first_name or "") + ((" " + ent.last_name) if ent.last_name else "")
        if not title and ent.username:
            title = ent.username
    else:
        kind = "peer"
        title = str(ent)
    return kind, title or "(no title)"

def dialog_row_text(dialog) -> str:
    ent = dialog.entity
    kind, title = label_of_entity(ent)
    uname = getattr(ent, "username", None)
    return f"[{kind}] {title}{(' @'+uname) if uname else ''}"

def msg_media_type(m: Message) -> Optional[str]:
    if isinstance(m.media, MessageMediaPhoto):
        return "photo"
    if isinstance(m.media, MessageMediaDocument):
        if m.document and m.document.mime_type:
            mt = m.document.mime_type
            if mt.startswith("video/"): return "video"
            if mt.startswith("audio/"): return "audio"
        return "document"
    return None

def extract_name_size(m: Message) -> Tuple[str, Optional[int]]:
    t = msg_media_type(m)
    name = ""
    size = None
    if t == "photo":
        name = (m.file and getattr(m.file, "name", None)) or "photo.jpg"
        size = getattr(m.file, "size", None)
    elif t in {"video","audio","document"}:
        if m.document:
            for attr in m.document.attributes:
                if hasattr(attr, "file_name") and attr.file_name:
                    name = attr.file_name
                    break
            if not name:
                name = (m.file and getattr(m.file, "name", None)) or "file"
            size = getattr(m.document, "size", None)
        else:
            name = (m.file and getattr(m.file, "name", None)) or "file"
            size = getattr(m.file, "size", None)
    else:
        name = "unknown"
    return name, size

class MediaItem:
    __slots__ = ("msg_id","date","type","name","size","message")
    def __init__(self, msg: Message):
        self.msg_id = msg.id
        self.date = msg.date
        self.type = msg_media_type(msg) or "unknown"
        self.name, self.size = extract_name_size(msg)
        self.message = msg

class PagedScanner:
    def __init__(self, client: TelegramClient, entity, batch_size=BATCH_SIZE, since_date_str=SINCE_DATE):
        self.client = client
        self.entity = entity
        self.batch_size = batch_size
        self.pages: List[List[MediaItem]] = []
        self.page_offsets: List[int] = [] 
        self.finished = False
        self.since_dt = datetime.strptime(since_date_str, "%Y-%m-%d") if since_date_str else None

    async def _scan_next_page(self):
        if self.finished:
            return False

        offset_id = self.page_offsets[-1] if self.page_offsets else 0
        collected: List[MediaItem] = []
        oldest_id_in_batch = None

        async for msg in self.client.iter_messages(self.entity, limit=1000, offset_id=offset_id):
            if self.since_dt and msg.date.replace(tzinfo=None) < self.since_dt:
                self.finished = True
                break
            if msg.media:
                t = msg_media_type(msg)
                if t:
                    collected.append(MediaItem(msg))
                    if len(collected) >= self.batch_size:
                        oldest_id_in_batch = msg.id
                        break
            oldest_id_in_batch = msg.id

        if not collected:
            self.finished = True
            return False

        self.pages.append(collected)
        self.page_offsets.append(oldest_id_in_batch if oldest_id_in_batch is not None else 0)
        return True

    async def get_page(self, index: int) -> Optional[List[MediaItem]]:
        while len(self.pages) <= index and not self.finished:
            ok = await self._scan_next_page()
            if not ok:
                break
        if index < len(self.pages):
            return self.pages[index]
        return None

async def list_dialogs(client: TelegramClient) -> List:
    dialogs = []
    async for d in client.iter_dialogs():
        ent = d.entity
        if HIDE_BOT_DM and isinstance(ent, User) and ent.bot:
            continue
        dialogs.append(d)
    dialogs.sort(key=lambda d: dialog_row_text(d).lower())
    return dialogs

def run_dialog_picker(dialogs: List) -> int:
    def _picker(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        h, w = stdscr.getmaxyx()
        header = "Dialog Picker - Press ↑/↓ to navigate, Q to quit, Enter to select"
        pad_top, pad_bottom = 2, 1
        page_size = max(5, h - (pad_top + pad_bottom + 1))
        idx = 0
        off = 0
        def redraw():
            stdscr.clear()
            stdscr.addnstr(0, 0, header, w-1, curses.A_BOLD)
            stdscr.addnstr(1, 0, "-"*(w-1), w-1)
            for i in range(page_size):
                di = off + i
                if di >= len(dialogs): break
                text = dialog_row_text(dialogs[di])
                if len(text) > w-4: text = text[:w-7] + "..."
                attr = curses.A_REVERSE if di == idx else curses.A_NORMAL
                stdscr.addnstr(2+i, 2, text, w-4, attr)
            pos = f"{idx+1}/{len(dialogs)}"
            stdscr.addnstr(h-1, 0, pos.ljust(w-1), w-1, curses.A_DIM)
            stdscr.refresh()
        redraw()
        while True:
            ch = stdscr.getch()
            if ch in (ord('q'), ord('Q')): return -1
            elif ch == curses.KEY_UP:
                if idx > 0:
                    idx -= 1
                    if idx < off: off = idx
                redraw()
            elif ch == curses.KEY_DOWN:
                if idx < len(dialogs)-1:
                    idx += 1
                    if idx >= off + page_size: off = idx - page_size + 1
                redraw()
            elif ch in (10, 13):
                return idx
    return curses.wrapper(_picker)

def draw_media_page(stdscr, page_items: List[MediaItem], current_page: int, selected_ids: Set[int], cursor: int):
    h, w = stdscr.getmaxyx()
    pad_top, pad_bottom = 3, 2
    page_height = max(5, h - (pad_top + pad_bottom + 1))
    title = f"Media Picker | Page {current_page+1} (batch {BATCH_SIZE}) | W/S: up/down, → select, ← cancel, ↑ prev page, ↓ next page, Enter to continue, q to cancel"
    stdscr.clear()
    stdscr.addnstr(0, 0, title, w-1, curses.A_BOLD)
    stdscr.addnstr(1, 0, "-"*(w-1), w-1)

    if not page_items:
        stdscr.addnstr(3, 2, "No items on this page.", w-4)
        stdscr.refresh()
        return 0

    cursor = max(0, min(cursor, len(page_items)-1))
    start = max(0, min(cursor - (page_height-1)//2, max(0, len(page_items)-page_height)))
    for i in range(page_height):
        di = start + i
        if di >= len(page_items): break
        item = page_items[di]
        mark = "x" if item.msg_id in selected_ids else " "
        date_str = item.date.strftime("%Y-%m-%d %H:%M")
        size_str = human_size(item.size)
        row = f"[{mark}] {item.msg_id} | {date_str} | {item.type:<8} | {size_str:>8} | {item.name}"
        if len(row) > w-2: row = row[:w-5] + "..."
        attr = curses.A_REVERSE if di == cursor else curses.A_NORMAL
        stdscr.addnstr(2+i, 2, row, w-4, attr)

    footer = f"Selected: {len(selected_ids)}"
    stdscr.addnstr(h-1, 0, footer.ljust(w-1), w-1, curses.A_DIM)
    stdscr.refresh()
    return cursor

def media_picker_one_page(page_items: List[MediaItem], current_page: int, selected_ids: Set[int], cursor: int):
    def _picker(stdscr):
        curses.curs_set(0)
        stdscr.keypad(True)
        c = draw_media_page(stdscr, page_items, current_page, selected_ids, cursor)
        cursor_local = c
        while True:
            ch = stdscr.getch()
            if ch in (ord('q'), ord('Q')): return ('quit', cursor_local, False)
            elif ch in (10, 13):          return ('confirm', cursor_local, False)
            elif ch in (ord('w'), ord('W')):
                if page_items and cursor_local > 0: cursor_local -= 1
                draw_media_page(stdscr, page_items, current_page, selected_ids, cursor_local)
            elif ch in (ord('s'), ord('S')):
                if page_items and cursor_local < len(page_items)-1: cursor_local += 1
                draw_media_page(stdscr, page_items, current_page, selected_ids, cursor_local)
            elif ch == curses.KEY_RIGHT:
                if page_items:
                    mid = page_items[cursor_local].msg_id
                    selected_ids.add(mid)
                draw_media_page(stdscr, page_items, current_page, selected_ids, cursor_local)
            elif ch == curses.KEY_LEFT:
                if page_items:
                    mid = page_items[cursor_local].msg_id
                    selected_ids.discard(mid)
                draw_media_page(stdscr, page_items, current_page, selected_ids, cursor_local)
            elif ch == curses.KEY_UP:     return ('prev', cursor_local, False)
            elif ch == curses.KEY_DOWN:   return ('next', cursor_local, False)
            else:
                pass
    return curses.wrapper(_picker)

async def resolve_entity(client: TelegramClient, ent):
    if isinstance(ent, Channel) and getattr(ent, "access_hash", None) is not None:
        return InputPeerChannel(ent.id, ent.access_hash)
    return ent

async def download_selected(items: List[MediaItem], out_dir: str):
    ensure_dir(out_dir)
    ok = fail = 0
    print(f"\nDownloading {len(items)} file...")
    print(f"Output directory: {out_dir}")

    progress = Progress(
        TextColumn("[bold blue]{task.fields[filename]}", justify="right"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    )

    with progress:
        for it in items:
            subdir = os.path.join(out_dir, it.type)
            ensure_dir(subdir)

            filename_display = (it.name if len(it.name) <= 30 else it.name[:27] + "...")
            task_id = progress.add_task("", filename=filename_display, total=it.size or 0)

            def cb(downloaded, total):
                progress.update(task_id, completed=downloaded, total=total or it.size or 0)

            try:
                path = await it.message.download_media(file=subdir, progress_callback=cb)
                if path and os.path.exists(path):
                    base = os.path.basename(path)
                    newp = os.path.join(subdir, f"{it.msg_id}_{base}")
                    if newp != path:
                        os.replace(path, newp)
                    ok += 1
                else:
                    fail += 1
            except FloodWaitError as e:
                progress.console.print(f"[yellow]WAIT[/] Rate limit {e.seconds}s…")
                await asyncio.sleep(e.seconds + 1)
            except Exception as e:
                fail += 1
                progress.console.print(f"[red]FAIL[/] {it.msg_id}: {e}")

            progress.remove_task(task_id)

    print(f"\nDone. Success: {ok}, Failed: {fail}")

async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    dialogs = await list_dialogs(client)
    if not dialogs:
        print("Nothing to show. No dialogs found.")
        await client.disconnect()
        return

    sel = run_dialog_picker(dialogs)
    if sel is None or sel < 0:
        print("Cancelled.")
        await client.disconnect()
        return

    picked = dialogs[sel].entity
    kind, title = label_of_entity(picked)
    shown = f"{title} ({kind})"
    uname = getattr(picked, "username", None)
    if uname: shown += f" @{uname}"
    print(f"\nSelected: {shown}")

    entity = await resolve_entity(client, picked)

    scanner = PagedScanner(client, entity, batch_size=BATCH_SIZE, since_date_str=SINCE_DATE)

    current_page = 0
    selected_ids: Set[int] = set()
    cursor = 0

    page_items = await scanner.get_page(current_page)
    if not page_items:
        print("No media items found in this dialog.")
        await client.disconnect()
        return

    while True:
        action, cursor, _ = media_picker_one_page(page_items, current_page, selected_ids, cursor)

        if action == 'quit':
            print("Cancelled.")
            await client.disconnect()
            return
        elif action == 'confirm':
            chosen: List[MediaItem] = []
            for pg in scanner.pages:
                for it in pg:
                    if it.msg_id in selected_ids:
                        chosen.append(it)
            if not chosen:
                print("No files selected. Cancelled.")
                await client.disconnect()
                return
            ensure_dir(OUTPUT_DIR)
            await download_selected(chosen, OUTPUT_DIR)
            await client.disconnect()
            return
        elif action == 'next':
            next_page = current_page + 1
            next_items = await scanner.get_page(next_page)
            if next_items:
                current_page = next_page
                page_items = next_items
                cursor = min(cursor, max(0, len(page_items)-1))
            else:
                pass
        elif action == 'prev':
            if current_page > 0:
                current_page -= 1
                page_items = await scanner.get_page(current_page)
                cursor = min(cursor, max(0, len(page_items)-1))
            else:
                pass
        else:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTerminated by user.")
