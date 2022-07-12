#!/usr/bin/python
# -*- coding: utf-8 -*-

from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Gio
from gi.repository.GdkPixbuf import Pixbuf
import re
import os
import requests
import shutil
import threading
import subprocess
import json


class Camera(object):

    def __init__(self, ip='10.5.5.9'):
        self.url = 'http://' + ip + '/videos/DCIM/100GOPRO/'
        self._active_status = False
        self._arr = []

    def _get_len(self, t):
        n = 0
        for i in self._arr:
            if t in i:
                n += 1
        return n

    def _save_file(self, file):
        try:
            r = requests.get(self.url + file, timeout=5.0, stream=True)
            with open('/tmp/.gopro.cache', 'wb') as f:
                total_length = r.headers.get('content-length')
                dl = 0
                for chunk in r.iter_content(1024):
                    dl += len(chunk)
                    pr = int(float(dl) / float(total_length) * 100)
                    f.write(chunk)
                    yield pr
        except:
            yield None

    def update_content(self):
        GLib.idle_add(APP.st_buttons, False)
        self._arr = []
        try:
            res = requests.get(self.url, timeout=5.0).text
            result = re.finditer(
                r'href="(G[^.]+.[JPG|MP4]+)"', res, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            for match in result:
                if not os.path.exists(Settings.get('path_to_save') + "/" + match.groups()[0]):
                    self._arr.append(match.groups()[0])
            GLib.idle_add(APP.print_sb, "{0} New Photo / {1} New Video".format(
                self._get_len('JPG'), self._get_len('MP4')
            ))
        except:
            GLib.idle_add(APP.print_sb, "Not connecting to GoPro")
        GLib.idle_add(APP.st_buttons, True)

    def download(self):
        GLib.idle_add(APP.st_buttons, False)
        downl_complete = 0
        n = self._get_len('JPG') if Settings.get('only_inage') else len(self._arr)
        if n > 0:
            for i in self._arr:
                if 'MP4' in i and Settings.get('only_inage'):
                    pass
                else:
                    for progress in self._save_file(i):
                        if progress:
                            GLib.idle_add(
                                APP.print_sb,
                                "Downloading, {2} of {3} / {0} {1}%".format(
                                    i, progress, downl_complete, n
                                )
                            )
                            if progress == 100:
                                downl_complete += 1
                                shutil.copyfile(
                                    '/tmp/.gopro.cache',
                                    Settings.get('path_to_save') + "/" + i
                                )
                                GLib.idle_add(APP.print_t, Settings.get('path_to_save') + "/" + i, i)
                        else:
                            GLib.idle_add(APP.print_sb, "Not connecting to GoPro")
            self.update_content()
        else:
            GLib.idle_add(APP.print_sb, "No new photos")
        GLib.idle_add(APP.st_buttons, True)


class GoProApp(Gtk.Window):

    def __init__(self):
        Gtk.Window.__init__(self, title="GoProApp")
        self.set_size_request(500, 100)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_border_width(0)
        #self.set_resizable(False)
        self.connect('delete-event', self.quit)

        self.hb = Gtk.HeaderBar()
        self.hb.set_show_close_button(True)
        self.set_titlebar(self.hb)

        self.button_update = Gtk.Button("Update")
        self.button_update.connect("clicked", self._on_b_update)
        self.hb.pack_start(self.button_update)

        self.button_download_photo = Gtk.Button("Download")
        self.button_download_photo.connect("clicked", self._on_b_download_photo)
        self.hb.pack_start(self.button_download_photo)

        self.btn_img = Gtk.Image.new_from_stock(Gtk.STOCK_PROPERTIES, Gtk.IconSize.LARGE_TOOLBAR)
        self.button_set = Gtk.Button()
        self.button_set.connect("clicked", self._on_b_set)
        self.button_set.set_image(self.btn_img)
        self.hb.pack_end(self.button_set)
        #self.hb.props.title = "GoPro Hero Downloader"

        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.add(self.vbox)

        self.liststore = Gtk.ListStore(Pixbuf, str, bool)
        self.iconview = Gtk.IconView.new()
        self.iconview.set_model(self.liststore)
        self.iconview.set_pixbuf_column(0)
        self.iconview.set_text_column(1)
        self.iconview.props.item_width = 0
        self.iconview.props.margin = 14
        self.iconview.props.row_spacing = 0
        self.iconview.props.column_spacing = 6
        self.iconview.props.item_padding = 0
        #self.iconview.props.columns = 3
        self.iconview.props.spacing = 0
        self.iconview.connect("selection-changed", self._on_icon_view_selection_changed)

        self.scroll = Gtk.ScrolledWindow()
        self.scroll.set_size_request(500, 400)
        self.scroll.add(self.iconview)
        self.vbox.pack_start(self.scroll, True, True, 0)

        self.statusbar = Gtk.Statusbar()
        self.context = self.statusbar.get_context_id("info")
        self.vbox.pack_start(self.statusbar, False, False, 0)

    def _on_icon_view_selection_changed(self, widget):
        selected_path = widget.get_selected_items()[0]
        selected_iter = widget.get_model().get_iter(selected_path)
        img_name = widget.get_model().get_value(selected_iter, 1)
        img_path = Settings.get('path_to_save') + "/" + img_name
        print img_path
        threading.Thread(target=self._open_file, args=(img_path,)).start()

    def _open_file(self, img_path):
        p = subprocess.Popen('xdg-open '+img_path,
                             shell=True,
                             stderr=subprocess.PIPE,
                             stdout=subprocess.PIPE,
                             stdin=subprocess.PIPE)

    def _on_b_update(self, button):
        threading.Thread(target=CAMERA.update_content).start()

    def _on_b_download_photo(self, button):
        threading.Thread(target=CAMERA.download).start()

    def _on_folder_clicked(self, button):
        dialog = Gtk.FileChooserDialog(
            "Please choose a folder", self, Gtk.FileChooserAction.SELECT_FOLDER,
            (Gtk.STOCK_CANCEL, Gtk.ResponseType.CANCEL, "Select", Gtk.ResponseType.OK))
        dialog.set_current_folder(Settings.get('path_to_save'))
        response = dialog.run()
        if response == Gtk.ResponseType.OK:
            Settings.change('path_to_save', dialog.get_filename())
        elif response == Gtk.ResponseType.CANCEL:
            print "Cancel clicked"
        dialog.destroy()

    def _on_cb_clicked(self, button):
        if button.get_active():
            Settings.change('only_inage', True)
        else:
            Settings.change('only_inage', False)

    def _on_b_set(self, button):
        vbox = Gtk.Box.new(1, 0)
        vbox = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)

        hbox = Gtk.Box.new(1, 0)
        hbox = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 0)
        hbox.pack_start(vbox, True, True, 12)

        cb = Gtk.CheckButton.new_with_label("Downloading Only Image")
        cb.connect("toggled", self._on_cb_clicked)
        if Settings.get('only_inage'):
            cb.set_active(True)
        vbox.pack_start(cb, True, True, 12)

        button_choose = Gtk.Button("Choose Folder To Save")
        button_choose.connect("clicked", self._on_folder_clicked)
        vbox.pack_start(button_choose, True, True, 12)

        popover = Gtk.Popover.new(button)
        popover.set_relative_to(button)
        popover.set_modal(True)
        popover.set_position(Gtk.PositionType.BOTTOM)
        popover.add(hbox)
        popover.show_all()

    def print_t(self, text, name):
        try:
            pixbuf = Pixbuf.new_from_file_at_size(text, 150, 150)
        except:
            pixbuf = Pixbuf.new_from_file_at_size(os.path.dirname(__file__)+'/icons/'+'u.png', 150, 150)
        self.liststore.append([pixbuf, name, True])

    def st_buttons(self, b):
        self.button_update.set_sensitive(b)
        self.button_download_photo.set_sensitive(b)
        self.button_set.set_sensitive(b)

    def print_sb(self, text):
        self.statusbar.push(self.context, text)

    def quit(self, w, w2):
        Gtk.main_quit()
        subprocess.Popen('kill ' + str(os.getpid()), shell=True)


class Settings(object):
    path = os.path.join(os.getenv("HOME"), ".config") + "/gopro_downloader.cfg"
    _arr = {}
    _arr_st = {
        'path_to_save': os.path.join(os.getenv("HOME"), "GoPro"),
        'only_inage': True
    }

    @staticmethod
    def init():
        try:
            f = open(Settings.path, 'r')
            txt = f.read()
            Settings._arr = {
                'path_to_save': json.loads(txt)['path_to_save'],
                'only_inage': json.loads(txt)['only_inage']
            }
            f.close()
        except:
            with open(Settings.path, 'w') as f:
                json.dump(Settings._arr_st, f, ensure_ascii=False)
            Settings._arr = Settings._arr_st

    @staticmethod
    def get(n):
        return Settings._arr[n]

    @staticmethod
    def change(tar, val):
        Settings._arr[tar] = val
        with open(Settings.path, 'w') as f:
            json.dump(Settings._arr, f, ensure_ascii=False)


if __name__ == '__main__':
    Settings.init()
    APP = GoProApp()
    APP.show_all()
    CAMERA = Camera()
    threading.Thread(target=CAMERA.update_content).start()
    Gtk.main()
