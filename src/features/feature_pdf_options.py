"""
PDF options
Post-processes saved PDFs with Ghostscript: PDF/A-2b for long-term archiving
and/or smaller files (downsampled, recompressed images).
"""

import os
import shutil
import subprocess

from features import BaseFeature

SIZES = {"standard": None, "smaller": "/ebook", "smallest": "/screen"}


class Feature(BaseFeature):
    """PDF/A archiving and file-size options"""

    id = "pdf_options"
    name = "PDF options (PDF/A, smaller files)"
    description = "Save PDFs as PDF/A-2b for archiving and/or shrink them (Ghostscript)."
    default_enabled = False
    order = 60

    def postprocess_pdf(self, path):
        """Rewrite the PDF with Ghostscript per the chosen options"""
        pdfa = self.option("pdfa", True)
        size = SIZES.get(self.option("size", "standard"))
        if not (pdfa or size) or not shutil.which("gs"):
            return
        tmp = path + ".gs.pdf"
        cmd = ["gs", "-q", "-dBATCH", "-dNOPAUSE", "-dSAFER", "-sDEVICE=pdfwrite", f"-sOutputFile={tmp}"]
        if pdfa:
            cmd += ["-dPDFA=2", "-dPDFACompatibilityPolicy=1", "-sColorConversionStrategy=RGB"]
        if size:
            cmd += [f"-dPDFSETTINGS={size}"]
        r = subprocess.run(cmd + [path], capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and os.path.getsize(tmp) > 0:
            os.replace(tmp, path)
        else:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise RuntimeError(f"Ghostscript failed: {r.stderr.strip()[-200:]}")

    def settings_widget(self, ctx):
        """PDF/A switch and size choice"""
        import gi

        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk

        box = Gtk.Box(spacing=12)
        check = Gtk.CheckButton(label="PDF/A-2b (archival)")
        check.set_active(self.option("pdfa", True))
        check.connect("toggled", lambda c: self.set_option("pdfa", c.get_active()))
        box.pack_start(check, False, False, 0)
        combo = Gtk.ComboBoxText()
        for key, label in (
            ("standard", "Standard size"),
            ("smaller", "Smaller (150 dpi images)"),
            ("smallest", "Smallest (72 dpi)"),
        ):
            combo.append(key, label)
        combo.set_active_id(self.option("size", "standard"))
        combo.connect("changed", lambda c: self.set_option("size", c.get_active_id()))
        box.pack_start(combo, False, False, 0)
        return box
