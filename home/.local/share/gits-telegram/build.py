#!/usr/bin/env python3
"""Build the Ghost in the Shell theme for Telegram Desktop (.tdesktop-theme).

  ./build.py [output_dir]      # default ~/Downloads

A .tdesktop-theme is a zip: colors.tdesktop-theme (name: #rrggbb; lines) + an optional background.jpg.
Only colours that exist in the installed Telegram are written (checked against the strings of the binary),
so a renamed key in a newer release is skipped instead of breaking the theme. Palette = kitty.theme.
"""
import os
import re
import subprocess
import sys
import zipfile

TG_BIN = "/var/lib/flatpak/app/org.telegram.desktop/current/active/files/bin/Telegram"
WALL = os.path.expanduser("~/.local/share/gits/wallpapers/gits_smoke.png")

BG, ALT, SURF, RIP = "#060A14", "#0A1226", "#0C1A33", "#12294A"
LINE, FG, DIM, MUTED, FAINT, WHITE = "#254F5D", "#C8F4FF", "#9FC5D6", "#596977", "#3F4C5C", "#DDF9FF"
CY, CYHI, RED, GRN, YEL = "#2ED3D7", "#5EF1F5", "#E5432B", "#34D399", "#E8C547"
OUT_BG, OUT_SEL, IN_SEL = "#0E3B47", "#1B6070", "#254F5D"

COLORS = {
    # window / text
    "windowBg": BG, "windowFg": FG, "windowBgOver": SURF, "windowBgRipple": RIP, "windowFgOver": WHITE,
    "windowSubTextFg": MUTED, "windowSubTextFgOver": DIM, "windowBoldFg": CYHI, "windowBoldFgOver": CYHI,
    "windowBgActive": CY, "windowFgActive": BG, "windowActiveTextFg": CYHI, "windowShadowFg": "#000000",
    "shadowFg": "#00000040", "slideFadeOutBg": "#00000060",
    # buttons
    "activeButtonBg": CY, "activeButtonBgOver": CYHI, "activeButtonBgRipple": CYHI, "activeButtonFg": BG,
    "activeButtonFgOver": BG, "activeButtonSecondaryFg": BG, "activeButtonSecondaryFgOver": BG,
    "lightButtonBg": SURF, "lightButtonBgOver": RIP, "lightButtonBgRipple": LINE, "lightButtonFg": CYHI,
    "lightButtonFgOver": CYHI, "attentionButtonFg": RED, "attentionButtonFgOver": RED,
    "attentionButtonBgOver": "#E5432B22", "attentionButtonBgRipple": "#E5432B44",
    "outlineButtonBg": BG, "outlineButtonBgOver": SURF, "outlineButtonOutlineFg": CY, "outlineButtonBgRipple": RIP,
    # menus, boxes, tooltips
    "menuBg": ALT, "menuBgOver": SURF, "menuBgRipple": RIP, "menuIconFg": MUTED, "menuIconFgOver": CY,
    "menuSeparatorFg": LINE, "menuFgDisabled": FAINT, "boxBg": ALT, "boxTextFg": FG, "boxTitleFg": CYHI,
    "boxTextFgGood": GRN, "boxTextFgError": RED, "boxDivider": BG, "boxDividerBg": BG, "boxDividerFg": LINE,
    "tooltipBg": ALT, "tooltipFg": FG, "tooltipBorderFg": LINE,
    # inputs, scrollbars, sliders
    "inputBorderFg": LINE, "inputBorderFgOver": DIM, "inputBorderFgActive": CY, "placeholderFg": MUTED,
    "placeholderFgActive": MUTED, "filterInputBorderFg": CY, "filterInputInactiveBg": SURF, "filterInputActiveBg": SURF,
    "scrollBarBg": "#2ED3D766", "scrollBarBgOver": "#2ED3D7B3", "scrollBg": "#00000000", "scrollBgOver": SURF,
    "sliderBgInactive": LINE, "sliderBgActive": CY, "checkboxFg": LINE, "radialFg": CY,
    "searchedBarBg": ALT, "searchedBarBorder": LINE, "searchedBarFg": MUTED,
    "smallCloseIconFg": MUTED, "smallCloseIconFgOver": DIM,
    # title bar
    "titleBg": BG, "titleBgActive": BG, "titleFg": MUTED, "titleFgActive": FG,
    "titleButtonBg": BG, "titleButtonFg": MUTED, "titleButtonBgOver": SURF, "titleButtonFgOver": FG,
    "titleButtonBgActive": BG, "titleButtonFgActive": DIM, "titleButtonBgActiveOver": SURF, "titleButtonFgActiveOver": WHITE,
    "titleButtonCloseBg": BG, "titleButtonCloseFg": MUTED, "titleButtonCloseBgOver": RED, "titleButtonCloseFgOver": WHITE,
    "titleButtonCloseBgActive": BG, "titleButtonCloseFgActive": DIM,
    "titleButtonCloseBgActiveOver": RED, "titleButtonCloseFgActiveOver": WHITE,
    # side bar (folders)
    "sideBarBg": ALT, "sideBarBgActive": SURF, "sideBarBgRipple": RIP, "sideBarTextFg": DIM,
    "sideBarTextFgActive": CYHI, "sideBarIconFg": MUTED, "sideBarIconFgActive": CY,
    "sideBarBadgeBg": CY, "sideBarBadgeBgMuted": LINE, "sideBarBadgeFg": BG,
    # chat list: the selected chat is a solid cyan block, like the active tab in kitty / the browser
    "dialogsBg": BG, "dialogsBgOver": SURF, "dialogsBgActive": CY, "dialogsNameFg": FG, "dialogsNameFgOver": WHITE,
    "dialogsNameFgActive": BG, "dialogsChatIconFg": DIM, "dialogsChatIconFgOver": DIM, "dialogsChatIconFgActive": BG,
    "dialogsDateFg": MUTED, "dialogsDateFgOver": MUTED, "dialogsDateFgActive": BG, "dialogsTextFg": MUTED,
    "dialogsTextFgOver": MUTED, "dialogsTextFgActive": BG, "dialogsTextFgService": DIM, "dialogsTextFgServiceOver": DIM,
    "dialogsTextFgServiceActive": BG, "dialogsDraftFg": RED, "dialogsDraftFgOver": RED, "dialogsDraftFgActive": BG,
    "dialogsSendingIconFg": MUTED, "dialogsSentIconFg": CY, "dialogsSentIconFgActive": BG,
    "dialogsUnreadBg": CY, "dialogsUnreadBgOver": CY, "dialogsUnreadBgActive": BG, "dialogsUnreadBgMuted": LINE,
    "dialogsUnreadBgMutedOver": LINE, "dialogsUnreadBgMutedActive": BG, "dialogsUnreadFg": BG,
    "dialogsUnreadFgOver": BG, "dialogsUnreadFgActive": CY, "dialogsRippleBg": RIP, "dialogsRippleBgActive": CYHI,
    "dialogsMenuIconFg": MUTED, "dialogsMenuIconFgOver": CY, "dialogsForwardBg": SURF, "dialogsForwardFg": FG,
    # messages
    "msgInBg": SURF, "msgInBgSelected": IN_SEL, "msgOutBg": OUT_BG, "msgOutBgSelected": OUT_SEL,
    "msgInShadow": "#00000000", "msgInShadowSelected": "#00000000", "msgOutShadow": "#00000000",
    "msgOutShadowSelected": "#00000000", "msgSelectOverlay": "#2ED3D733",
    "historyTextInFg": FG, "historyTextInFgSelected": WHITE, "historyTextOutFg": WHITE, "historyTextOutFgSelected": WHITE,
    "historyLinkInFg": CYHI, "historyLinkInFgSelected": CYHI, "historyLinkOutFg": CYHI, "historyLinkOutFgSelected": CYHI,
    "msgInDateFg": MUTED, "msgInDateFgSelected": DIM, "msgOutDateFg": "#7FB8C4", "msgOutDateFgSelected": "#9FD3DE",
    "msgInReplyBarColor": CY, "msgInReplyBarSelColor": CYHI, "msgOutReplyBarColor": CYHI, "msgOutReplyBarSelColor": WHITE,
    "msgServiceFg": DIM, "msgServiceBg": "#0C1A33CC", "msgServiceBgSelected": "#254F5DCC",
    "msgWaveformInActive": CY, "msgWaveformInInactive": LINE, "msgWaveformOutActive": CYHI, "msgWaveformOutInactive": "#2A7684",
    "msgInMonoFg": GRN, "msgOutMonoFg": GRN, "msgInServiceFg": CY, "msgOutServiceFg": CYHI,
    # composer / history chrome
    "historyComposeAreaBg": ALT, "historyComposeAreaFg": FG, "historyComposeAreaFgService": MUTED,
    "historyComposeIconFg": MUTED, "historyComposeIconFgOver": CY, "historySendIconFg": CY, "historySendIconFgOver": CYHI,
    "historyReplyBg": ALT, "historyReplyIconFg": CY, "historyReplyCancelFg": MUTED, "historyReplyCancelFgOver": DIM,
    "historyToDownBg": SURF, "historyToDownBgOver": RIP, "historyToDownBgRipple": LINE, "historyToDownFg": CY,
    "historyToDownFgOver": CYHI, "historyToDownShadow": "#00000066",
    "historyScrollBarBg": "#2ED3D766", "historyScrollBarBgOver": "#2ED3D7B3", "historyScrollBg": "#00000000",
    "historyScrollBgOver": SURF, "historyUnreadBarBg": SURF, "historyUnreadBarFg": CYHI, "historyUnreadBarBorder": LINE,
    "topBarBg": ALT, "emojiPanBg": ALT, "emojiPanCategories": ALT, "emojiPanHeaderFg": MUTED,
    "emojiPanHeaderBg": ALT, "emojiPanHover": SURF,
}


def known_keys():
    """Every string of the installed Telegram binary that looks like a palette key."""
    out = subprocess.run(["strings", "-n", "4", TG_BIN], capture_output=True, text=True, check=True).stdout
    return set(re.findall(r"^[a-z][A-Za-z0-9]{3,60}$", out, re.M))


def background(dst):
    """Very dark, softly blurred version of the desktop wallpaper: readable text, still has the mood."""
    from PIL import Image, ImageEnhance, ImageFilter

    im = Image.open(WALL).convert("RGB")
    im.thumbnail((1920, 1080))
    im = im.filter(ImageFilter.GaussianBlur(6))
    im = ImageEnhance.Brightness(im).enhance(0.16)
    im.save(dst, "JPEG", quality=82)


def main():
    out_dir = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/Downloads")
    os.makedirs(out_dir, exist_ok=True)
    known = known_keys()
    ok = {k: v for k, v in COLORS.items() if k in known}
    skipped = sorted(set(COLORS) - set(ok))

    text = "// Ghost in the Shell for Telegram Desktop (generated by ~/.local/share/gits-telegram/build.py)\n"
    text += "".join(f"{k}: {v};\n" for k, v in ok.items())

    bg_path = os.path.join(out_dir, ".gits-background.jpg")
    try:
        background(bg_path)
    except Exception as exc:  # the theme works without a wallpaper
        bg_path = None
        print("no wallpaper:", exc)

    target = os.path.join(out_dir, "GhostInTheShell.tdesktop-theme")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("colors.tdesktop-theme", text)
        if bg_path:
            z.write(bg_path, "background.jpg")
    if bg_path:
        os.remove(bg_path)
    print(f"{len(ok)} colours written, {len(skipped)} skipped (not in this Telegram): {', '.join(skipped) or '-'}")
    print(target)


if __name__ == "__main__":
    main()
