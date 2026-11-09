#!/usr/bin/env python3
# Patch UI Acropolize (dijalankan oleh workflow sebelum build).
# Setiap patch memeriksa jumlah kecocokan; kalau source berbeda dari perkiraan, build berhenti dengan pesan jelas.
import re

M = 'app/src/main'
S = M + '/cpp/samp'


def rd(p):
    with open(p, encoding='latin-1', newline='') as f:
        return f.read()


def wr(p, s):
    with open(p, 'w', encoding='latin-1', newline='') as f:
        f.write(s)


def patch(s, pat, new, name, count=1, flags=re.S):
    n = len(re.findall(pat, s, flags))
    assert n == count, 'PATCH GAGAL [%s]: ditemukan %d, seharusnya %d' % (name, n, count)
    return re.sub(pat, lambda m: new, s, flags=flags)


# ------------------------------------------------------------------ 1. Musik/audio stream
p = S + '/audiostream.cpp'
s = rd(p)
s = patch(s, r'//if \(!BASS_Init\(-1, 44100, 0\)\) return false;[^\n]*',
          'if (!BASS_Init(-1, 44100, 0, NULL, NULL) && BASS_ErrorGetCode() != 14) '
          'FLog("BASS_Init gagal: %d", BASS_ErrorGetCode()); // fix: audio stream butuh BASS_Init (14 = sudah aktif)',
          'audio init')
s = patch(s, r'BASS_ChannelPlay\(bassStream, 0\);',
          'if (!bassStream) FLog("Stream gagal dibuka: %d", BASS_ErrorGetCode());\n\tBASS_ChannelPlay(bassStream, 0);',
          'audio log')
wr(p, s)
print('OK  audio stream')

# ------------------------------------------------------------------ 2. Perintah /q dan /quit
p = S + '/gui/samp_widgets/chat.cpp'
s = rd(p)
s = patch(s, r'#include <algorithm>', '#include <algorithm>\n#include <cctype>', 'chat include')
s = patch(s,
          r"if \(input\[0\] == '/'\) pNetGame->SendChatCommand\(input\.c_str\(\)\);\s*else pNetGame->SendChatMessage\(input\.c_str\(\)\);",
          "if (input[0] == '/')\n"
          "\t\t{\n"
          "\t\t\t// Perintah client seperti di PC: /q dan /quit langsung keluar dari game\n"
          "\t\t\tstd::string low = input;\n"
          "\t\t\twhile (!low.empty() && (low.back() == ' ' || low.back() == '\\r' || low.back() == '\\n')) low.pop_back();\n"
          "\t\t\tfor (size_t i = 0; i < low.size(); i++) low[i] = (char)tolower((unsigned char)low[i]);\n"
          "\t\t\tif (low == \"/q\" || low == \"/quit\")\n"
          "\t\t\t{\n"
          "\t\t\t\tpGame->bIsGameExiting = true;\n"
          "\t\t\t\tpNetGame->GetRakClient()->Disconnect(0);\n"
          "\t\t\t\tpJavaWrapper->exitGame();\n"
          "\t\t\t\treturn;\n"
          "\t\t\t}\n"
          "\t\t\tpNetGame->SendChatCommand(input.c_str());\n"
          "\t\t}\n"
          "\t\telse pNetGame->SendChatMessage(input.c_str());",
          'chat /q')
wr(p, s)
print('OK  perintah /q')

# ------------------------------------------------------------------ 3. Tap textdraw jangan bocor ke analog
p = S + '/net/textdrawpool.cpp'
s = rd(p)
a = s.index('bool CTextDrawPool::onTouchEvent')
b = s.index('void CTextDrawPool::SnapshotProcess')
seg = s[a:b]
k = seg.rfind('return true;')
assert k > 0 and seg.count('return true;') == 2, 'PATCH GAGAL [textdraw touch]: struktur fungsi berbeda'
seg = seg[:k] + 'return false; // fix: mode pilih textdraw, jangan teruskan sentuhan ke analog' + seg[k + len('return true;'):]
wr(p, s[:a] + seg + s[b:])
print('OK  sentuhan textdraw')

# ------------------------------------------------------------------ 4. Renderer: kotak membulat + tombol kaca
p = S + '/gui/imguirenderer.h'
s = rd(p)
s = patch(s, r'(void\s+drawRect\(const ImVec2& a, const ImVec2& b, const ImColor& color, bool fill = false, float thickness = 1\.0f\);)',
          'void drawRect(const ImVec2& a, const ImVec2& b, const ImColor& color, bool fill = false, float thickness = 1.0f);\n'
          '\tvoid drawRoundedRect(const ImVec2& a, const ImVec2& b, const ImColor& color, float rounding, bool fill = false);\n'
          '\tvoid drawGlassButton(const ImVec2& a, const ImVec2& b, const ImColor& base, bool focused);',
          'renderer.h')
wr(p, s)

p = S + '/gui/imguirenderer.cpp'
s = rd(p)
new_funcs = r'''void ImGuiRenderer::drawRect(const ImVec2& a, const ImVec2& b, const ImColor& color, bool fill, float thickness)
{
	fill ? m_drawList->AddRectFilled(a, b, color) :
		m_drawList->AddRect(a, b, color, 0.0f, 15, thickness);
}

void ImGuiRenderer::drawRoundedRect(const ImVec2& a, const ImVec2& b, const ImColor& color, float rounding, bool fill)
{
	fill ? m_drawList->AddRectFilled(a, b, color, rounding) :
		m_drawList->AddRect(a, b, color, rounding);
}

// Tombol gaya "kaca gelap" dengan garis emas (tema Acropolize)
void ImGuiRenderer::drawGlassButton(const ImVec2& a, const ImVec2& b, const ImColor& base, bool focused)
{
	float r = (b.y - a.y) * 0.30f;
	float alpha = base.Value.w;
	if (alpha < 0.55f) alpha = 0.55f; // jangan terlalu transparan

	// bayangan halus
	m_drawList->AddRectFilled(ImVec2(a.x, a.y + 2.0f), ImVec2(b.x, b.y + 2.0f), ImColor(0.0f, 0.0f, 0.0f, 0.30f), r);

	if (focused)
	{
		m_drawList->AddRectFilled(a, b, ImColor(1.0f, 0.83f, 0.0f, 0.92f), r);
	}
	else
	{
		m_drawList->AddRectFilled(a, b, ImColor(0.05f, 0.055f, 0.08f, alpha), r);
		// kilau tipis di sisi atas
		m_drawList->AddRectFilled(ImVec2(a.x + r, a.y + 1.0f), ImVec2(b.x - r, a.y + 2.5f), ImColor(1.0f, 1.0f, 1.0f, 0.10f));
	}

	ImColor border = focused ? ImColor(1.0f, 0.95f, 0.55f, 1.0f) : ImColor(1.0f, 0.83f, 0.0f, 0.85f);
	m_drawList->AddRect(a, b, border, r);
	m_drawList->AddRect(a + ImVec2(1.0f, 1.0f), b - ImVec2(1.0f, 1.0f), border, r > 1.5f ? r - 1.0f : r);
}'''
s = patch(s, r'void ImGuiRenderer::drawRect\(const ImVec2& a, const ImVec2& b, const ImColor& color, bool fill, float thickness\)\s*\{.*?\n\}',
          new_funcs, 'renderer.cpp')
wr(p, s)
print('OK  renderer')

# ------------------------------------------------------------------ 5. Tombol HUD (TAB/ESC/Y/>>) dan Spawn/panah
p = S + '/gui/widgets/button.cpp'
s = rd(p)
# Cocok untuk 3 tombol: Button biasa (Spawn, panah) serta CButton dan OButton (versi HUD, memakai hudAlpha)
btn_pat = (r'renderer->drawRect\(absolutePosition\(\), absolutePosition\(\) \+ size\(\),\s*'
           r'(hudAlpha\()?focused\(\) \? m_colorFocused : m_color\)?, true\);.*?UISettings::outlineSize\(\)\);')
n = len(re.findall(btn_pat, s, re.S))
assert n == 3, 'PATCH GAGAL [button draw]: ditemukan %d, seharusnya 3' % n


def btn_repl(m):
    base = 'hudAlpha(m_color)' if m.group(1) else 'm_color'
    return ('renderer->drawGlassButton(absolutePosition(), absolutePosition() + size(), ' + base + ', focused());\n'
            '\tm_label->setColor(focused() ? ImColor(0.07f, 0.07f, 0.07f) : ImColor(1.0f, 1.0f, 1.0f));')


s = re.sub(btn_pat, btn_repl, s, flags=re.S)
wr(p, s)
print('OK  tombol HUD')

# ------------------------------------------------------------------ 6. Keyboard bawaan: transparan, input di atas
p = S + '/gui/samp_widgets/keyboard.cpp'
s = rd(p)

s = patch(s, r'void Keyboard::performLayout\(\)\s*\{.*?\n\}',
          '''void Keyboard::performLayout()
{
	// Gaya baru: tombol di bawah layar (kaca transparan), kolom input di bawah chat agar chat tetap terlihat
	float rowH = UISettings::keyboardRowHeight();
	float keysH = rowH * 5.0f;
	float parentH = (parent() && parent()->height() > 0.0f) ? parent()->height() : ImGui::GetIO().DisplaySize.y;
	float inputRelY = parentH * 0.235f - position().y;

	m_input->setFixedSize(ImVec2(width() * 0.86f, rowH));
	m_input->setPosition(ImVec2(width() * 0.07f, inputRelY));

	KeyboardLayout* layouts[5] = { m_layoutLowerENG, m_layoutUpperENG, m_layoutLowerRU, m_layoutUpperRU, m_layoutNUM };
	for (int i = 0; i < 5; i++)
	{
		layouts[i]->setFixedSize(ImVec2(width(), keysH));
		layouts[i]->setPosition(ImVec2(0.0f, height() - keysH));
	}

	Widget::performLayout();
}''', 'keyboard layout')

s = patch(s, r'void Keyboard::draw\(ImGuiRenderer\* renderer\)\s*\{.*?\n\}',
          '''void Keyboard::draw(ImGuiRenderer* renderer)
{
	// panel tombol: kaca gelap transparan + garis emas tipis
	float rad = UISettings::padding() * 0.9f;
	renderer->drawRoundedRect(absolutePosition(), absolutePosition() + size(), ImColor(0.03f, 0.04f, 0.07f, 0.50f), rad, true);
	renderer->drawRoundedRect(absolutePosition(), absolutePosition() + size(), ImColor(1.0f, 0.83f, 0.0f, 0.45f), rad, false);
	Widget::draw(renderer);
}''', 'keyboard draw')

s = patch(s, r'void KeyboardInput::draw\(ImGuiRenderer\* renderer\)\s*\{.*?\n\}',
          '''void KeyboardInput::draw(ImGuiRenderer* renderer)
{
	float font_sz = UISettings::fontSize();
	float rad = height() * 0.5f;
	renderer->drawRoundedRect(absolutePosition(), absolutePosition() + size(), ImColor(0.03f, 0.04f, 0.07f, 0.80f), rad, true);
	renderer->drawRoundedRect(absolutePosition(), absolutePosition() + size(), ImColor(1.0f, 0.83f, 0.0f, 0.85f), rad, false);

	ImVec2 textPos = absolutePosition() + ImVec2(UISettings::padding() * 1.2f, (height() - font_sz) / 2);
	if (m_caption.empty())
	{
		renderer->drawText(textPos, ImColor(1.0f, 1.0f, 1.0f, 0.35f), std::string("Ketik pesan atau /perintah..."), false, font_sz);
	}
	else
	{
		renderer->drawText(textPos, ImColor(1.0f, 1.0f, 1.0f), m_caption, false, font_sz);
	}

	// kursor berkedip di ujung teks
	if (((int)(ImGui::GetTime() * 2.0)) % 2 == 0)
	{
		ImVec2 ts = renderer->calculateTextSize(m_caption, font_sz);
		float cx = textPos.x + ts.x + 2.0f;
		renderer->drawLine(ImVec2(cx, textPos.y), ImVec2(cx, textPos.y + font_sz), ImColor(1.0f, 0.83f, 0.0f), 2.0f);
	}

	Widget::draw(renderer);
}''', 'keyboard input draw')

s = patch(s, r'if \(focused\(\)\) renderer->drawRect\(absolutePosition\(\), absolutePosition\(\) \+ size\(\), ImColor\(0xF5, 0x91, 0x32\), true\);',
          '''{
		// tombol keyboard: kapsul kaca transparan, emas saat ditekan
		float inset = UISettings::outlineSize();
		ImVec2 ka = absolutePosition() + ImVec2(inset, inset);
		ImVec2 kb = absolutePosition() + size() - ImVec2(inset, inset);
		float krad = height() * 0.22f;
		if (focused()) renderer->drawRoundedRect(ka, kb, ImColor(1.0f, 0.83f, 0.0f, 0.85f), krad, true);
		else if (m_extendedKey == ExtendedKey::SEND) renderer->drawRoundedRect(ka, kb, ImColor(1.0f, 0.83f, 0.0f, 0.80f), krad, true);
		else renderer->drawRoundedRect(ka, kb, ImColor(1.0f, 1.0f, 1.0f, m_extendedKey == ExtendedKey::NONE ? 0.10f : 0.17f), krad, true);
	}''', 'key draw')

m = re.search(r'case ExtendedKey::SEND:\s*renderer->drawTriangle\(.*?ImColor\(1\.0f, 1\.0f, 1\.0f\), true', s, re.S)
assert m, 'PATCH GAGAL [send glyph]'
seg = m.group(0).replace('ImColor(1.0f, 1.0f, 1.0f), true', 'ImColor(0.07f, 0.07f, 0.07f), true')
s = s[:m.start()] + seg + s[m.end():]
wr(p, s)
print('OK  keyboard')

p = S + '/gui/uisettings.cpp'
s = rd(p)
s = patch(s, r'ImVec2 UISettings::m_keyboardPos = ImVec2\(0\.0f, 180\.0f[^;]*\);', 'ImVec2 UISettings::m_keyboardPos = ImVec2(0.0f, 274.0f);', 'ui pos')
s = patch(s, r'ImVec2 UISettings::m_keyboardSize = ImVec2\(640\.0f, 300\.0f\);', 'ImVec2 UISettings::m_keyboardSize = ImVec2(640.0f, 206.0f);', 'ui size')
s = patch(s, r'float UISettings::m_keyboardRowHeight = 52\.0f;', 'float UISettings::m_keyboardRowHeight = 40.0f;', 'ui row')
wr(p, s)

p = S + '/gui/gui.cpp'
s = rd(p)
s = patch(s, r'if \(m_keyboard->visible\(\) && m_keyboard->contains\(pos\)\)',
          'if (m_keyboard->visible() && (m_keyboard->contains(pos) || m_keyboard->input()->contains(pos)))', 'gui touch')
wr(p, s)
print('OK  ukuran keyboard dan sentuhan')

# ------------------------------------------------------------------ 7. Launcher: keyboard bawaan jadi default untuk instalasi baru
p = M + '/java/com/samp/mobile/launcher/AcropolizeLauncherActivity.java'
with open(p, encoding='utf-8', newline='') as f:
    s = f.read()
assert s.count('androidkeyboard = true') == 1, 'PATCH GAGAL [launcher keyboard]'
s = s.replace('androidkeyboard = true', 'androidkeyboard = false')
with open(p, 'w', encoding='utf-8', newline='') as f:
    f.write(s)
print('OK  launcher default keyboard')

# ------------------------------------------------------------------ 8. Bilah input keyboard Android (3 tombol pink -> emas)
D = M + '/res/drawable/'
files = {
    'acro_kb_bar.xml': '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="16dp"/>
    <solid android:color="#CC101018"/>
    <stroke android:width="1dp" android:color="#66FFD400"/>
</shape>
''',
    'acro_kb_btn.xml': '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="12dp"/>
    <gradient android:type="linear" android:angle="0"
        android:startColor="#FFFFE14D"
        android:endColor="#FFFFB800"/>
</shape>
''',
}
for name, body in files.items():
    with open(D + name, 'w', encoding='utf-8', newline='') as f:
        f.write(body)

p = M + '/res/layout/layout_keyboard.xml'
with open(p, encoding='utf-8', newline='') as f:
    s = f.read()
assert s.count('android:background="#65FFFFFF"') == 1, 'PATCH GAGAL [layout bar]'
assert s.count('@drawable/ic_buttoncolor') == 3, 'PATCH GAGAL [layout tombol]'
assert s.count('android:textColor="#000000"') == 1, 'PATCH GAGAL [layout teks]'
assert s.count('android:textStyle="bold" />') == 3, 'PATCH GAGAL [layout bold]'
s = s.replace('android:background="#65FFFFFF"', 'android:background="@drawable/acro_kb_bar"')
s = s.replace('@drawable/ic_buttoncolor', '@drawable/acro_kb_btn')
s = s.replace('android:textColor="#000000"', 'android:textColor="#FFFFFFFF"')
s = s.replace('android:textStyle="bold" />', 'android:textColor="#FF111111"\n            android:textStyle="bold" />')
with open(p, 'w', encoding='utf-8', newline='') as f:
    f.write(s)
print('OK  bilah input keyboard Android')
print('SEMUA PATCH UI BERHASIL')
