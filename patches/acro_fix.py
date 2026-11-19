#!/usr/bin/env python3
# acro_fix.py - SATU patch untuk client SA-MP Android Acropolize (dijalankan workflow sebelum build).
# Menggabungkan semua tahap lama (UI, audio, keyboard, textdraw, kontrol, kendaraan, senjata, sync).
# Tiap patch memeriksa jumlah kecocokan; bila source berbeda dari perkiraan, build berhenti dengan pesan jelas.
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


def patch_keep(s, pat, fn, name, count=1, flags=re.S):
    """seperti patch(), tapi fn(match) -> teks pengganti (bisa memakai grup)"""
    n = len(re.findall(pat, s, flags))
    assert n == count, 'PATCH GAGAL [%s]: ditemukan %d, seharusnya %d' % (name, n, count)
    return re.sub(pat, fn, s, flags=flags)



# ======================================================================== BAGIAN 1 (acro_ui)
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
s = s[:a] + seg + s[b:]
s = patch(s, r'extern UI\* pUI;', 'extern UI* pUI;\nextern void (*AND_TouchEvent)(int type, int num, int posX, int posY);', 'textdraw extern')
s = patch(s, r'pGame->FindPlayerPed\(\)->TogglePlayerControllable\(false\);',
          'pGame->FindPlayerPed()->TogglePlayerControllable(false);\n'
          '        // fix: lepaskan semua jari yang mungkin masih "tertahan" di analog saat mode pilih dimulai\n'
          '        for (int i = 0; i < 3; i++) AND_TouchEvent(1, i, 0, 0);\n'
          '        FLog("SelectTextDraw: aktif");',
          'textdraw release')
wr(p, s)

# jari ke-2/3 harus dilepas dengan nomor yang sama (sebelumnya selalu jari ke-0 -> analog nyangkut)
p = S + '/game/hooks.cpp'
s = rd(p)
a = s.index('void AND_TouchEvent_hook(int type, int num, int posX, int posY)')
b = s.index('/* ====', a)
seg = s[a:b]
assert seg.count('AND_TouchEvent(1, 0, 0, 0)') == 3, 'PATCH GAGAL [hook sentuhan]: ditemukan %d' % seg.count('AND_TouchEvent(1, 0, 0, 0)')
seg = seg.replace('AND_TouchEvent(1, 0, 0, 0)', 'AND_TouchEvent(1, num, 0, 0)')
wr(p, s[:a] + seg + s[b:])
print('OK  sentuhan textdraw dan analog')

# ------------------------------------------------------------------ 3c. Catatan diagnosa mode pilih textdraw (siapa yang menyalakan/mematikan)
p = S + '/net/scriptrpc.cpp'
s = rd(p)
s = patch(s, r'pNetGame->GetTextDrawPool\(\)->SetSelectState\(bEnable \? true : false, dwColor\);',
          'FLog("ScrSelectTextDraw: enable=%d warna=0x%x", bEnable ? 1 : 0, dwColor);\n'
          '\tpNetGame->GetTextDrawPool()->SetSelectState(bEnable ? true : false, dwColor);',
          'log select rpc')
s = patch(s, r'void ScrPlayAudioStream\(RPCParameters\* rpcParams\)\s*\{',
          'void ScrPlayAudioStream(RPCParameters* rpcParams)\n{\n\tFLog("RPC PlayAudioStream diterima dari server");',
          'log audio rpc')
wr(p, s)
p = S + '/net/textdrawpool.cpp'
s = rd(p)
s = patch(s, r'pGame->DisplayHUD\(true\);', 'pGame->DisplayHUD(true);\n        FLog("SelectTextDraw: nonaktif");', 'log select off')
wr(p, s)
print('OK  catatan diagnosa textdraw dan audio')

# ------------------------------------------------------------------ 3d. Info debug di library native (supaya crash bisa dibaca sampai nama fungsi)
p = 'app/build.gradle'
with open(p, encoding='utf-8', newline='') as f:
    s = f.read()
pat = r"(ndk \{\s*abiFilters 'armeabi-v7a', 'arm64-v8a'\s*\})"
assert len(re.findall(pat, s)) == 1, 'PATCH GAGAL [gradle ndk]'
s = re.sub(pat, lambda m: m.group(1) + '\n\n        externalNativeBuild {\n            cmake {\n                cFlags "-g"\n                cppFlags "-g"\n            }\n        }', s)
with open(p, 'w', encoding='utf-8', newline='') as f:
    f.write(s)
print('OK  info debug native')

# ------------------------------------------------------------------ 3e. Pratinjau model textdraw: hemat memori dan aman di HP RAM kecil
p = S + '/game/snapshothelper.cpp'
s = rd(p)
# tekstur jangan dibuat dari raster kosong (crash di dalam library game)
s = patch(s, r'RwTexture\* bufferTexture = RwTextureCreate\(raster\);',
          'RwTexture* bufferTexture = raster ? RwTextureCreate(raster) : nullptr;', 'snapshot raster', count=3)
# model kendaraan/objek yang selesai dipakai pratinjau dilepas dari memori (sebelumnya tertahan terus)
s = patch(s, r'delete pVehicle;\s*return bufferTexture;',
          'delete pVehicle;\n        CStreaming::RemoveModelIfNoRefs(iModel); // fix: lepas model pratinjau dari memori\n        return bufferTexture;',
          'snapshot kendaraan')
s = patch(s, r'(DestroyAtomicOrClump\(reinterpret_cast<uintptr_t>\(pRwObject\)\);)\s*return bufferTexture;',
          'DestroyAtomicOrClump(reinterpret_cast<uintptr_t>(pRwObject));\n    CStreaming::RemoveModelIfNoRefs(iModel); // fix: lepas model pratinjau dari memori\n    return bufferTexture;',
          'snapshot objek')
# kalau kamera/lampu pratinjau gagal dibuat, jangan lanjut
s = patch(s, r'(RwTexture\* CSnapShotHelper::CreateObjectSnapShot\([^)]*\)\s*\{)', 
          'RwTexture* CSnapShotHelper::CreateObjectSnapShot(int iModel, uint32_t dwColor, CVector* vecRot, float fZoom)\n{\n    if (!m_camera || !m_light) return nullptr;',
          'guard objek')
s = patch(s, r'(RwTexture\* CSnapShotHelper::CreatePedSnapShot\([^)]*\)\s*\{)',
          'RwTexture* CSnapShotHelper::CreatePedSnapShot(int iModel, uint32_t dwColor, CVector* vecRot, float fZoom)\n{\n    if (!m_camera || !m_light) return nullptr;',
          'guard ped')
wr(p, s)
print('OK  pratinjau model hemat memori')

# ------------------------------------------------------------------ 3f. Catatan diagnosa lampu kendaraan (untuk ELM)
p = S + '/game/vehicle.cpp'
s = rd(p)
s = patch(s, r'(void CVehicle::UpdateDamageStatus\(uint32_t dwPanelDamage, uint32_t dwDoorDamage, uint8_t byteLightDamage\)\s*\{)',
          'void CVehicle::UpdateDamageStatus(uint32_t dwPanelDamage, uint32_t dwDoorDamage, uint8_t byteLightDamage)\n{\n'
          '\t{ static int s_n = 0; if (s_n < 300) { s_n++; FLog("UpdateDamageStatus: panel=%u pintu=%u lampu=%d", dwPanelDamage, dwDoorDamage, (int)byteLightDamage); } }',
          'log damage')
wr(p, s)
p = S + '/net/netrpc.cpp'
s = rd(p)
s = patch(s, r'pVehicle->ApplyLightState\(vehParamsEx\.byteLight\);',
          '{ static int s_n = 0; if (s_n < 300) { s_n++; FLog("VehicleParamsEx: mesin=%d lampu=%d", (int)vehParamsEx.byteEngine, (int)vehParamsEx.byteLight); } }\n'
          '\t\tpVehicle->ApplyLightState(vehParamsEx.byteLight);',
          'log paramsex')
wr(p, s)
print('OK  catatan diagnosa lampu')

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
pat = r'(String\[\]\[\] kv = \{\s*\{ "name", nick \})'
assert len(re.findall(pat, s)) == 1, 'PATCH GAGAL [launcher migrasi]'
s = re.sub(pat, lambda m: (
    '// Migrasi satu kali: pakai keyboard bawaan client (transparan) menggantikan keyboard sistem\n'
    '        if (!prefs.getBoolean("kb_native_v1", false)) {\n'
    '            for (int i = 0; i < lines.size(); i++) {\n'
    '                if (lines.get(i).trim().toLowerCase().startsWith("androidkeyboard")) lines.set(i, "androidkeyboard = false");\n'
    '            }\n'
    '            prefs.edit().putBoolean("kb_native_v1", true).apply();\n'
    '        }\n\n'
    '        ' + m.group(1)), s)
with open(p, 'w', encoding='utf-8', newline='') as f:
    f.write(s)
print('OK  launcher default keyboard dan migrasi')

# ------------------------------------------------------------------ 8. Bilah input keyboard Android (3 tombol pink -> emas)
D = M + '/res/drawable/'
files = {
    'acro_kb_bar.xml': '''<?xml version="1.0" encoding="utf-8"?>
<shape xmlns:android="http://schemas.android.com/apk/res/android" android:shape="rectangle">
    <corners android:radius="16dp"/>
    <solid android:color="#52FFFFFF"/>
    <stroke android:width="1.5dp" android:color="#99FFD400"/>
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
s = s.replace('android:textStyle="bold" />', 'android:textColor="#FF111111"\n            android:textStyle="bold" />')
with open(p, 'w', encoding='utf-8', newline='') as f:
    f.write(s)
print('OK  bilah input keyboard Android')
print('SEMUA PATCH UI BERHASIL')



# ======================================================================== BAGIAN 2 (acro_fix2)
# ---------------------------------------------------------------- 1. Audio stream
p = S + '/audiostream.cpp'
s = rd(p)

# a) Jangan pernah membisukan stream hanya karena IsGamePaused() (offset memori bisa salah di 2.10 -> volume 0 terus)
s = patch(s, r'if \(pGame->IsGamePaused\(\)\)\s*\{\s*BASS_SetConfig\(5, 0\);\s*\}\s*else\s*\{\s*BASS_SetConfig\(5, 5000\);\s*\}',
          'BASS_SetConfig(5, 10000); // fix: volume stream selalu penuh (voice plugin bisa menurunkannya ke 0)',
          'audio volume')

# b) Diagnosa lengkap di samp_log.txt + pastikan device jalan
s = patch(s, r'bassStream = BASS_StreamCreateURL\(g_szAudioStreamUrl, 0, 0x940000, 0,0\);',
          'FLog("Audio: device=%d started=%d url=%s", (int)BASS_GetDevice(), (int)BASS_IsStarted(), g_szAudioStreamUrl);\n'
          '\tBASS_Start();\n'
          '\tbassStream = BASS_StreamCreateURL(g_szAudioStreamUrl, 0, 0x940000, 0,0);\n'
          '\tif (!bassStream) FLog("Audio: StreamCreateURL gagal, kode=%d", (int)BASS_ErrorGetCode());',
          'audio create log')
s = patch(s, r'if \(!bassStream\) FLog\("Stream gagal dibuka: %d", BASS_ErrorGetCode\(\)\);\s*BASS_ChannelPlay\(bassStream, 0\);',
          'if (bassStream && !BASS_ChannelPlay(bassStream, 0)) FLog("Audio: ChannelPlay gagal, kode=%d", (int)BASS_ErrorGetCode());\n'
          '\telse if (bassStream) FLog("Audio: stream berjalan");',
          'audio play log')
wr(p, s)
print('OK  audio stream')

# ---------------------------------------------------------------- 2. Keyboard: kotak keyboard mencakup kolom input
p = S + '/gui/samp_widgets/keyboard.cpp'
s = rd(p)

s = patch(s, r'void Keyboard::performLayout\(\)\s*\{.*?\n\}',
          '''void Keyboard::performLayout()
{
	// Kotak keyboard SEKARANG mencakup kolom input + tombol, jadi sentuhan di kolom input
	// tidak dianggap "di luar keyboard" (dulu itu memanggil hide() dan tombol << >> / mati).
	float rowH = UISettings::keyboardRowHeight();
	float keysH = rowH * 5.0f;
	float parentH = (parent() && parent()->height() > 0.0f) ? parent()->height() : ImGui::GetIO().DisplaySize.y;
	float top = parentH * 0.235f;
	float totalH = parentH - top;
	if (totalH < keysH + rowH) totalH = keysH + rowH;

	setPosition(ImVec2(position().x, parentH - totalH));
	setFixedSize(ImVec2(width(), totalH));

	m_input->setFixedSize(ImVec2(width() * 0.86f, rowH));
	m_input->setPosition(ImVec2(width() * 0.07f, 0.0f));

	KeyboardLayout* layouts[5] = { m_layoutLowerENG, m_layoutUpperENG, m_layoutLowerRU, m_layoutUpperRU, m_layoutNUM };
	for (int i = 0; i < 5; i++)
	{
		layouts[i]->setFixedSize(ImVec2(width(), keysH));
		layouts[i]->setPosition(ImVec2(0.0f, totalH - keysH));
	}

	Widget::performLayout();
}''', 'kb layout v2')

s = patch(s, r'void Keyboard::draw\(ImGuiRenderer\* renderer\)\s*\{.*?\n\}',
          '''void Keyboard::draw(ImGuiRenderer* renderer)
{
	// panel kaca hanya di area tombol (area di atasnya tetap transparan agar chat terlihat)
	float keysH = UISettings::keyboardRowHeight() * 5.0f;
	float rad = UISettings::padding() * 0.9f;
	ImVec2 a = absolutePosition() + ImVec2(0.0f, height() - keysH);
	ImVec2 b = absolutePosition() + size();
	renderer->drawRoundedRect(a, b, ImColor(0.03f, 0.04f, 0.07f, 0.50f), rad, true);
	renderer->drawRoundedRect(a, b, ImColor(1.0f, 0.83f, 0.0f, 0.45f), rad, false);
	Widget::draw(renderer);
}''', 'kb draw v2')

# ---------------------------------------------------------------- 3. Hapus tombol RUS (sisakan 123 dan ENG)
s = patch(s, r'[ \t]*m_rows\[3\]->addKey\(ExtendedKey::LANG_RU\);[ \t]*\r?\n', '', 'hapus RUS', count=5)
# spasi dilebarkan supaya baris bawah tetap penuh
s = patch(s, r'addKey\(ExtendedKey::SPACE\)->setFixedSize\(ImVec2\(keySize\.x \* 3, 0\.0f\)\)',
          'addKey(ExtendedKey::SPACE)->setFixedSize(ImVec2(keySize.x * 4, 0.0f))', 'lebar spasi', count=4)
wr(p, s)
print('OK  keyboard (input bisa diklik, RUS dihapus)')
# ---------------------------------------------------------------- 4. Copy-paste: tombol "Tempel" di kolom input keyboard native
# getClipboardText() sudah ada di NvEventQueueActivity.java, tinggal dipanggil dari native lewat JNI
p = S + '/java/jniutil.h'
s = rd(p)
s = patch(s, r'jmethodID s_hideEditObject;', 'jmethodID s_hideEditObject;\n\tjmethodID s_getClipboard;', 'jni header')
wr(p, s)

p = S + '/java/jniutil.cpp'
s = rd(p)
s = patch(s, r's_hideEditObject = env->GetMethodID\(clas, "hideEditObject", "\(\)V"\);',
          's_hideEditObject = env->GetMethodID(clas, "hideEditObject", "()V");\n'
          '    s_getClipboard = env->GetMethodID(clas, "getClipboardText", "()[B");\n'
          '    if (env->ExceptionCheck()) env->ExceptionClear();', 'jni ctor')
CLIP_FN = '''
const char* CJavaWrapper::GetClipboardString()
{
    static std::string s_clip;
    s_clip.clear();

    JNIEnv* p = nullptr;
    javaVM->GetEnv((void**)&p, JNI_VERSION_1_6);
    if (!p || !s_getClipboard) return s_clip.c_str();

    jbyteArray arr = (jbyteArray)p->CallObjectMethod(activity, s_getClipboard);
    if (p->ExceptionCheck()) { p->ExceptionClear(); return s_clip.c_str(); }
    if (!arr) return s_clip.c_str();

    jsize len = p->GetArrayLength(arr);
    jbyte* e = p->GetByteArrayElements(arr, nullptr);
    if (e)
    {
        s_clip.assign((const char*)e, (size_t)len);
        p->ReleaseByteArrayElements(arr, e, JNI_ABORT);
    }
    p->DeleteLocalRef(arr);
    return s_clip.c_str();
}
'''
s = s.rstrip() + '\n' + CLIP_FN
wr(p, s)

p = S + '/gui/samp_widgets/keyboard.h'
s = rd(p)
s = patch(s, r'Button\* m_buttonTub;', 'Button* m_buttonTub;\n\tButton* m_buttonPaste;', 'kb header')
wr(p, s)

PASTE_CTOR = '''m_buttonTub = new Button("/", UISettings::fontSize());
	this->addChild(m_buttonTub);
	m_buttonPaste = new Button("Tempel", UISettings::fontSize());
	this->addChild(m_buttonPaste);
	m_buttonPaste->setCallback([]()
	{
		// tempel isi clipboard Android ke kolom input (satu baris, maks 255 karakter)
		std::string t = pJavaWrapper ? std::string(pJavaWrapper->GetClipboardString()) : std::string();
		for (auto& c : t) if (c == '\\r' || c == '\\n' || c == '\\t') c = ' ';
		size_t b = t.find_first_not_of(' ');
		if (b == std::string::npos) return;
		t = t.substr(b, t.find_last_not_of(' ') - b + 1);
		std::string cur = pUI->keyboard()->input()->inputString();
		if (cur.size() >= 255) return;
		if (cur.size() + t.size() > 255) t = t.substr(0, 255 - cur.size());
		pUI->keyboard()->input()->setInputString(cur + t);
	});
	m_buttonPaste->setVisible(true);'''
PASTE_LAYOUT = '''m_buttonNext->setPosition(
			ImVec2(width() - (m_buttonNext->width() + UISettings::padding()),
				   (height() - m_buttonNext->height()) / 2));
	m_buttonPaste->setPosition(
			ImVec2(m_buttonTub->position().x - (m_buttonPaste->width() + UISettings::padding()),
				   (height() - m_buttonPaste->height()) / 2));'''
p = S + '/gui/samp_widgets/keyboard.cpp'
s = rd(p)
s = patch(s, r'm_buttonTub = new Button\("/", UISettings::fontSize\(\)\);\s*this->addChild\(m_buttonTub\);', PASTE_CTOR, 'kb ctor paste')
s = patch(s, r'm_buttonNext->setPosition\(\s*ImVec2\(width\(\) - \(m_buttonNext->width\(\) \+ UISettings::padding\(\)\),\s*\(height\(\) - m_buttonNext->height\(\)\) / 2\)\);', PASTE_LAYOUT, 'kb layout paste')
wr(p, s)
print('OK  copy-paste (tombol Tempel)')

# ---------------------------------------------------------------- 5. Kunci analog/tombol game sebelum benar-benar spawn
p = S + '/net/localplayer.h'
s = rd(p)
s = patch(s, r'void DisableSurf\(\) \{ m_surfData\.bIsActive = false; \}',
          'void DisableSurf() { m_surfData.bIsActive = false; }\n\tbool IsSpawnedForInput() const { return m_bIsActive; }', 'lp accessor')
wr(p, s)

p = S + '/net/textdrawpool.h'
s = rd(p)
s = patch(s, r'bool GetState\(\) \{\s*return m_bSelectState;\s*\}',
          'bool GetState() {\n        return m_bSelectState;\n    }\n\n'
          '    bool HasAnyTextDraw() const {\n'
          '        for (int i = 0; i < MAX_TEXT_DRAWS; i++)\n'
          '            if (m_bSlotState[i] && m_pTextDraw[i]) return true;\n'
          '        return false;\n'
          '    }', 'tdpool any')
wr(p, s)

LOCK = '''
		// fix: selama BELUM spawn dan masih ada textdraw server -> analog dan tombol game dikunci.
		// Sentuhan hanya diteruskan ke textdraw (supaya tombol Spawn/pilih karakter bisa ditekan).
		if (pNetGame && pNetGame->GetGameState() == GAMESTATE_CONNECTED &&
			pNetGame->GetTextDrawPool() && pNetGame->GetPlayerPool() &&
			pNetGame->GetPlayerPool()->GetLocalPlayer() &&
			!pNetGame->GetPlayerPool()->GetLocalPlayer()->IsSpawnedForInput() &&
			pNetGame->GetTextDrawPool()->HasAnyTextDraw())
		{
			if (!(pUI->keyboard()->visible() || pUI->dialog()->visible()))
				pNetGame->GetTextDrawPool()->onTouchEvent(type, num, posX, posY);
			return AND_TouchEvent(1, num, 0, 0);
		}
'''
p = S + '/game/hooks.cpp'
s = rd(p)
anchor = r'(TouchType::pop\);\s*break;\s*\}\s*)(\s*if \(pUI->keyboard\(\)->visible\(\) \|\| pUI->dialog\(\)->visible\(\)\) \{)'
n = len(re.findall(anchor, s, re.S))
assert n == 1, 'PATCH GAGAL [hook lock]: ditemukan %d' % n
s = re.sub(anchor, lambda m: m.group(1) + LOCK + m.group(2), s, count=1, flags=re.S)
wr(p, s)
print('OK  kunci analog sebelum spawn')
print('SEMUA PATCH TAHAP 5 BERHASIL')



# ======================================================================== BAGIAN 3 (acro_fix3)
# ------------------------------------------------------------ 1. Kunci + sembunyikan kontrol bawaan GTA
p = S + '/game/hooks.cpp'
s = rd(p)

HELPER = '''// fix tahap 6: true = layar server (pilih karakter/spawn/SelectTextDraw) sedang aktif,
// analog dan tombol bawaan GTA harus disembunyikan dan tidak menerima sentuhan.
static bool AcroTouchControlsLocked()
{
	if (!pNetGame || pNetGame->GetGameState() != GAMESTATE_CONNECTED) return false;
	CTextDrawPool* pTD = pNetGame->GetTextDrawPool();
	if (!pTD) return false;
	if (pTD->GetState()) return true; // server memanggil SelectTextDraw
	CPlayerPool* pPP = pNetGame->GetPlayerPool();
	if (!pPP || !pPP->GetLocalPlayer()) return false;
	return !pPP->GetLocalPlayer()->IsSpawnedForInput() && pTD->HasAnyTextDraw();
}

void Render2dStuff()'''
s = patch(s, r'void Render2dStuff\(\)', HELPER, 'hooks helper')

s = patch(s,
          r'\(\(void\(\*\)\(bool\) \)\(g_libGTASA \+ \(VER_x32 \? 0x002B0BD8 \+ 1 : 0x36FB00\)\) \)\(false\); // CTouchInterface::DrawAll',
          'if (!AcroTouchControlsLocked()) // fix: sembunyikan analog/tombol bawaan saat layar pilih karakter\n'
          '        ((void(*)(bool) )(g_libGTASA + (VER_x32 ? 0x002B0BD8 + 1 : 0x36FB00)) )(false); // CTouchInterface::DrawAll',
          'hide DrawAll')

s = patch(s,
          r'if \(pNetGame && pNetGame->GetGameState\(\) == GAMESTATE_CONNECTED &&\s*pNetGame->GetTextDrawPool\(\) && pNetGame->GetPlayerPool\(\) &&.*?HasAnyTextDraw\(\)\)',
          'if (AcroTouchControlsLocked())', 'touch lock cond')
wr(p, s)
print('OK  kunci + sembunyikan kontrol bawaan')

# ------------------------------------------------------------ 2. Toleransi sentuh textdraw + log
p = S + '/net/textdrawpool.cpp'
s = rd(p)
s = patch(s, r'if \(!IsPointInRect\(x, y, &pTextDraw->m_rectArea\)\)\s*continue;',
          '''{
            // fix: toleransi 24 px supaya tombol Spawn/pilih karakter tidak harus tepat sasaran
            CRect rr = pTextDraw->m_rectArea;
            const float slop = 24.0f;
            rr.left -= slop; rr.bottom -= slop; rr.right += slop; rr.top += slop;
            if (!IsPointInRect(x, y, &rr))
                continue;
        }''', 'td slop')
s = patch(s, r'return false; // fix: mode pilih textdraw, jangan teruskan sentuhan ke analog',
          'if (type == TOUCH_POP) FLog("TD tidak kena tombol: x=%d y=%d", x, y);\n'
          '    return false; // fix: mode pilih textdraw, jangan teruskan sentuhan ke analog',
          'td miss log')
s = patch(s, r'm_wClickedTextDrawID = i;\s*pUI->PushToBufferedQueueTextDrawPressed\(\(uint16_t\)i\);',
          'm_wClickedTextDrawID = i;\n'
          '                FLog("TD diklik: id=%d x=%d y=%d", (int)i, x, y);\n'
          '                pUI->PushToBufferedQueueTextDrawPressed((uint16_t)i);',
          'td hit log')
wr(p, s)
print('OK  toleransi sentuh textdraw')

# ------------------------------------------------------------ 3. Ikon clipboard + input transparan
p = S + '/gui/samp_widgets/keyboard.cpp'
s = rd(p)

ICON_CLASS = '''/* Tombol tempel berbentuk ikon clipboard (tanpa teks) */
class PasteIconButton : public Button
{
public:
	PasteIconButton(float font_size) : Button("MM", font_size) {}

	virtual void draw(ImGuiRenderer* renderer) override
	{
		ImVec2 a = absolutePosition();
		ImVec2 sz = size();
		renderer->drawGlassButton(a, ImVec2(a.x + sz.x, a.y + sz.y), UISettings::buttonColor(), focused());

		ImColor ic = focused() ? ImColor(0.07f, 0.07f, 0.07f) : ImColor(1.0f, 1.0f, 1.0f);
		float s = (sz.x < sz.y ? sz.x : sz.y) * 0.5f;
		float cx = a.x + sz.x * 0.5f;
		float cy = a.y + sz.y * 0.5f;
		float x0 = cx - s * 0.55f, x1 = cx + s * 0.55f;
		float y0 = cy - s * 0.55f, y1 = cy + s * 0.75f;

		renderer->drawRoundedRect(ImVec2(x0, y0), ImVec2(x1, y1), ic, s * 0.12f, false);
		renderer->drawRoundedRect(ImVec2(cx - s * 0.32f, y0 - s * 0.18f), ImVec2(cx + s * 0.32f, y0 + s * 0.16f), ic, s * 0.08f, true);
		renderer->drawLine(ImVec2(x0 + s * 0.3f, cy + s * 0.02f), ImVec2(x1 - s * 0.3f, cy + s * 0.02f), ic, 2.0f);
		renderer->drawLine(ImVec2(x0 + s * 0.3f, cy + s * 0.40f), ImVec2(x1 - s * 0.3f, cy + s * 0.40f), ic, 2.0f);
	}
};

KeyboardInput::KeyboardInput()'''
s = patch(s, r'KeyboardInput::KeyboardInput\(\)', ICON_CLASS, 'icon class')
s = patch(s, r'm_buttonPaste = new Button\("Tempel", UISettings::fontSize\(\)\);',
          'm_buttonPaste = new PasteIconButton(UISettings::fontSize());', 'icon ctor')

s = patch(s,
          r'ImColor\(0\.03f, 0\.04f, 0\.07f, 0\.80f\), rad, true\);\s*renderer->drawRoundedRect\(absolutePosition\(\), absolutePosition\(\) \+ size\(\), ImColor\(1\.0f, 0\.83f, 0\.0f, 0\.85f\), rad, false\);',
          'ImColor(0.03f, 0.04f, 0.07f, 0.35f), rad, true);\n'
          '\trenderer->drawRoundedRect(absolutePosition(), absolutePosition() + size(), ImColor(1.0f, 0.83f, 0.0f, 0.55f), rad, false);',
          'input transparan')
wr(p, s)
print('OK  ikon clipboard + input transparan')

# ------------------------------------------------------------ 4. Sentuh di luar keyboard = tutup
p = S + '/gui/gui.cpp'
s = rd(p)
OUTSIDE = '''m_dialog->touchEvent(pos, type);
		return;
	}

	if (m_keyboard->visible())
	{
		// fix: sentuh di luar area keyboard -> tutup keyboard tanpa mengirim.
		// Hanya kalau sentuhan MULAI di luar (geser keluar dari tombol tidak menutup).
		static bool s_pushOutside = false;
		if (type == TouchType::push) s_pushOutside = true;
		else if (type == TouchType::pop)
		{
			if (s_pushOutside) m_keyboard->hide();
			s_pushOutside = false;
		}
		return;
	}'''
s = patch(s, r'm_dialog->touchEvent\(pos, type\);\s*return;\s*\}', OUTSIDE, 'touch luar keyboard')
wr(p, s)
print('OK  sentuh di luar menutup keyboard')

# ------------------------------------------------------------ 5. Ikon AFK lebih lambat
p = S + '/net/remoteplayer.cpp'
s = rd(p)
# jalan kaki: dulu AFK setelah 1,5 dtk tanpa paket sync (animasi repair tidak mengirim sync -> ikon palsu)
s = patch(s, r'if \(\(GetTickCount\(\) - m_dwLastRecvTick\) > 1500\) \{\s*m_bIsAFK = true;\s*\}',
          'if ((GetTickCount() - m_dwLastRecvTick) > 8000) { // fix: AFK baru setelah 8 dtk (dulu 1,5 dtk)\n'
          '\t\t\t\tm_bIsAFK = true;\n\t\t\t}', 'afk onfoot')
# berhenti bergerak tetap setelah 3 dtk tanpa paket, tidak lagi bergantung pada flag AFK
s = patch(s, r'if \(m_bIsAFK && \(\(GetTickCount\(\) - m_dwLastRecvTick\) > 3000\)\)',
          'if ((GetTickCount() - m_dwLastRecvTick) > 3000)', 'afk stop move')
# dalam kendaraan
s = patch(s, r'if \(\(GetTickCount\(\) - m_dwLastRecvTick\) > 1500\)\s*m_bIsAFK = true;',
          'if ((GetTickCount() - m_dwLastRecvTick) > 8000)\n\t\t\t\t\t\tm_bIsAFK = true;', 'afk incar moving')
m = list(re.finditer(r'(else if \(!m_bIsAFK\)\s*\{\s*)if \(\(GetTickCount\(\) - m_dwLastRecvTick\) > 3000\)', s, re.S))
assert len(m) == 1, 'PATCH GAGAL [afk incar idle]: ditemukan %d, seharusnya 1' % len(m)
s = s[:m[0].start()] + m[0].group(1) + 'if ((GetTickCount() - m_dwLastRecvTick) > 8000)' + s[m[0].end():]
wr(p, s)
print('OK  ambang AFK 8 detik')
print('SEMUA PATCH TAHAP 6 BERHASIL')



# ======================================================================== BAGIAN 4 (acro_fix4)
# ------------------------------------------------------------ 1. Mod kendaraan: ANTRE, terapkan aman di game thread
# Penyebab crash lama: AddComponent dipanggil langsung di dalam RPC saat kendaraan dibuat (model komponen dimuat
# sambil game thread berjalan, objek RW kendaraan belum siap, atau kendaraan berada di interior lain).
# Sekarang mod disimpan dulu, lalu dipasang 1 komponen per giliran oleh CVehiclePool::Process (game thread),
# hanya bila kendaraan siap, interior sama dengan pemain, dan model komponen sudah termuat (tanpa memblokir).
# Penjaga crash: bila game mati saat memasang komponen X, X masuk modblock.txt sehingga tidak crash berulang.
p = S + '/net/vehiclepool.h'
s = rd(p)
PH = """uint32_t		m_dwLastUndrivenProcessTick[MAX_VEHICLES];

public:
	struct PendingMod {
		bool active; uint32_t tickStart; uint32_t tickNext; uint8_t interior;
		uint8_t nComps; uint8_t next; int16_t comps[14];
		uint8_t paint; int body1; int body2; bool colorDone;
	};
	PendingMod m_pendingMod[MAX_VEHICLES];
	void ProcessPendingMods(uint32_t dwTick);"""
s = patch(s, r'uint32_t\s+m_dwLastUndrivenProcessTick\[MAX_VEHICLES\];', PH, 'pool.h pending')
wr(p, s)

p = S + '/net/vehiclepool.cpp'
s = rd(p)
MODS = """m_pVehicles[new_veh->VehicleID]->SetHealth(new_veh->fHealth);

    // fix: mod (velg, NOS, dll), paintjob dan warna body diantre, dipasang aman oleh ProcessPendingMods
    {
        PendingMod& pm = m_pendingMod[new_veh->VehicleID];
        memset(&pm, 0, sizeof(pm));
        for (int i = 0; i < 14; i++)
            if (new_veh->byteModSlots[i]) pm.comps[pm.nComps++] = (int16_t)(new_veh->byteModSlots[i] + 999);
        pm.paint = new_veh->bytePaintJob;
        pm.body1 = new_veh->iBodyColor1;
        pm.body2 = new_veh->iBodyColor2;
        pm.interior = new_veh->byteInterior;
        pm.tickStart = GetTickCount();
        pm.tickNext = pm.tickStart + 1200;
        pm.active = (pm.nComps || pm.paint || pm.body1 != -1 || pm.body2 != -1);
    }"""
s = patch(s, r'm_pVehicles\[new_veh->VehicleID\]->SetHealth\(new_veh->fHealth\);', MODS, 'vehicle mods')
s = patch_keep(s, r'(bool CVehiclePool::Delete\(VEHICLEID VehicleID\)\s*\{\s*if\(!GetSlotState\(VehicleID\) \|\| !m_pVehicles\[VehicleID\]\)\s*return false;)',
               lambda m: m.group(1) + '\n\n    m_pendingMod[VehicleID].active = false;', 'pool Delete')
PROC = """
// fix: pasang mod kendaraan secara aman (dipanggil dari Process = game thread)
static std::set<int> s_blockedComps;
static bool s_modGuardInit = false;
static void ModGuardPath(char* out, const char* name) { sprintf(out, "%sSAMP/%s", g_pszStorage, name); }

void CVehiclePool::ProcessPendingMods(uint32_t dwTick)
{
    char path[256];
    if (!s_modGuardInit)
    {
        s_modGuardInit = true;
        ModGuardPath(path, "modblock.txt");
        if (FILE* f = fopen(path, "r")) { int id; while (fscanf(f, "%d", &id) == 1) s_blockedComps.insert(id); fclose(f); }
        ModGuardPath(path, "modguard.txt");
        if (FILE* f = fopen(path, "r"))
        {
            int id = 0;
            if (fscanf(f, "%d", &id) == 1 && id > 0)
            {
                s_blockedComps.insert(id);
                char bp[256]; ModGuardPath(bp, "modblock.txt");
                if (FILE* o = fopen(bp, "a")) { fprintf(o, "%d\\n", id); fclose(o); }
                FLog("Mod kendaraan: komponen %d diblokir karena run sebelumnya crash saat memasangnya", id);
            }
            fclose(f);
            remove(path);
        }
    }

    if (!pGame || !pGame->FindPlayerPed()) return;
    int budget = 1;
    for (VEHICLEID id = 0; id < MAX_VEHICLES && budget > 0; id++)
    {
        PendingMod& pm = m_pendingMod[id];
        if (!pm.active) continue;
        CVehicle* pVeh = m_pVehicles[id];
        if (!pVeh || !m_bVehicleSlotState[id] || !pVeh->m_pVehicle) { pm.active = false; continue; }
        if (dwTick < pm.tickNext) continue;
        if (dwTick - pm.tickStart > 20000) { pm.active = false; FLog("Mod kendaraan %d: dibatalkan (timeout)", (int)id); continue; }
        if (pGame->GetActiveInterior() != pm.interior) { pm.tickNext = dwTick + 500; continue; }
        if (!pVeh->m_pVehicle->m_pRwObject || !GamePool_Vehicle_GetAt(pVeh->m_dwGTAId)) { pm.tickNext = dwTick + 300; continue; }

        if (pm.next < pm.nComps)
        {
            int comp = pm.comps[pm.next];
            if (s_blockedComps.count(comp)) { pm.next++; continue; }
            if (!CStreaming::GetInfo(comp).IsLoaded())
            {
                CStreaming::RequestModel(comp, STREAMING_GAME_REQUIRED | STREAMING_KEEP_IN_MEMORY);
                CStreaming::LoadAllRequestedModels(false);
                pm.tickNext = dwTick + 150;
                if (dwTick - pm.tickStart > 15000) pm.next++;
                continue;
            }
            ModGuardPath(path, "modguard.txt");
            if (FILE* f = fopen(path, "w")) { fprintf(f, "%d\\n", comp); fflush(f); fclose(f); }
            try { pVeh->AddComponent(comp); } catch (...) { FLog("Mod kendaraan gagal: veh=%d mod=%d", (int)id, comp); }
            remove(path);
            pm.next++;
            pm.tickNext = dwTick + 120;
            budget--;
            continue;
        }
        if (pm.paint) { pVeh->SetPaintJob(pm.paint - 1); pm.paint = 0; }
        if (!pm.colorDone && (pm.body1 != -1 || pm.body2 != -1))
        {
            pVeh->SetColor((uint8_t)(pm.body1 != -1 ? pm.body1 : 0), (uint8_t)(pm.body2 != -1 ? pm.body2 : 0));
            pm.colorDone = true;
        }
        FLog("Kendaraan %d: mod diterapkan (%d komponen)", (int)id, (int)pm.nComps);
        pm.active = false;
    }
}

void CVehiclePool::Process()
{
    ProcessPendingMods(GetTickCount());"""
s = patch(s, r'\nvoid CVehiclePool::Process\(\)\s*\{', PROC, 'Process hook')
if '#include <set>' not in s:
    s = s.replace('#include "vehiclepool.h"', '#include "vehiclepool.h"\n#include "../game/Streaming.h"\n#include "../game/util.h"', 1)
    s = '#include <set>\n#include <cstdio>\n' + s
wr(p, s)
print('OK  mod kendaraan (antrean aman + penjaga crash)')

# ------------------------------------------------------------ 2. Senjata: tangan kosong
p = S + '/game/Entity/CPedGTA.cpp'
s = rd(p)
s = patch_keep(s, r'(void CPedGTA::GiveWeapon\(int iWeaponID, int iAmmo\)\s*\{)',
               lambda m: m.group(1) + '''
    if (iWeaponID == 0)
    {
        // fix tahap 7: tangan kosong -> lepaskan senjata yang sedang dipegang.
        // Dulu id 0 tidak punya model sehingga fungsi keluar tanpa efek dan senjata lama tetap terpegang/menembak.
        CHook::CallFunction<void>(g_libGTASA + (VER_x32 ? 0x004A521C + 1 : 0x59B86C), this, 0); // CPed::SetCurrentWeapon
        return;
    }
''', 'giveweapon fist')
wr(p, s)
print('OK  senjata: tangan kosong')

# ------------------------------------------------------------ 3. Heartbeat sync jalan kaki
p = S + '/net/localplayer.cpp'
s = rd(p)
s = patch(s, r'if \(/\*\(GetTickCount\(\) - m_dwLastUpdateOnFootData\) > 500 \|\| \*/memcmp\(&m_ofSync, &ofSync, sizeof\(ONFOOT_SYNC_DATA\)\)\)',
          'if ((GetTickCount() - m_dwLastUpdateOnFootData) > 700 || memcmp(&m_ofSync, &ofSync, sizeof(ONFOOT_SYNC_DATA))) // fix: kirim ulang saat diam, kalau tidak PC menganggap AFK',
          'onfoot heartbeat')
wr(p, s)
print('OK  heartbeat sync jalan kaki (anti-AFK palsu di PC)')

# ------------------------------------------------------------ 4. Textdraw: pilih kandidat dengan luas terkecil
p = S + '/net/textdrawpool.cpp'
s = rd(p)
NEW_TOUCH = '''bool CTextDrawPool::onTouchEvent(int type, bool multi, int x, int y)
{
    if (!m_bSelectState)
        return true;

    m_wClickedTextDrawID = 0xFFFF;

    // fix tahap 7: dari semua textdraw selectable yang tersentuh, ambil yang LUASNYA PALING KECIL.
    // Server sering memasang textdraw selectable transparan selebar layar (id tinggi) untuk menangkap klik di luar.
    // Dulu textdraw itu selalu menang sehingga tombol Spawn / pilih karakter tidak pernah menerima sentuhan.
    int best = -1;
    float bestArea = 3.4e38f;
    int candidates = 0;

    for (int i = MAX_TEXT_DRAWS - 1; i >= 0; i--)
    {
        if (!m_bSlotState[i] || !m_pTextDraw[i])
            continue;

        CTextDraw* pTextDraw = m_pTextDraw[i];
        pTextDraw->m_bHovered = false;
        pTextDraw->m_dwHoverColor = 0;

        if (!pTextDraw->m_TextDrawData.byteSelectable)
            continue;

        CRect rr = pTextDraw->m_rectArea;
        float w = rr.right - rr.left;
        float h = rr.top - rr.bottom;
        const float slop = 24.0f; // toleransi sentuh
        rr.left -= slop; rr.bottom -= slop; rr.right += slop; rr.top += slop;
        if (!IsPointInRect(x, y, &rr))
            continue;

        candidates++;
        float area = (w > 0.0f ? w : 0.0f) * (h > 0.0f ? h : 0.0f);
        if (area < bestArea)
        {
            bestArea = area;
            best = i;
        }
    }

    if (best < 0)
    {
        if (type == TOUCH_POP) FLog("TD tidak kena tombol: x=%d y=%d", x, y);
        return false; // mode pilih textdraw, jangan teruskan sentuhan ke analog
    }

    CTextDraw* pHit = m_pTextDraw[best];
    switch (type)
    {
        case TOUCH_PUSH:
        case TOUCH_MOVE:
            pHit->m_bHovered = true;
            pHit->m_dwHoverColor = m_dwHoverColor;
            break;

        case TOUCH_POP:
            m_wClickedTextDrawID = (uint16_t)best;
            FLog("TD diklik: id=%d x=%d y=%d kandidat=%d", best, x, y, candidates);
            pUI->PushToBufferedQueueTextDrawPressed((uint16_t)best);
            pHit->m_bHovered = false;
            pHit->m_dwHoverColor = 0;
            break;
    }
    return false;
}
'''
s = patch(s, r'bool CTextDrawPool::onTouchEvent\(int type, bool multi, int x, int y\)\n\{.*?\n\}\n', NEW_TOUCH, 'td smallest area')
wr(p, s)
print('OK  textdraw: pilih area terkecil')

# ------------------------------------------------------------ 5. Kunci juga saat server membekukan pemain
p = S + '/net/scriptrpc.cpp'
s = rd(p)
s = patch(s, r'// 0\.3\.7\s*void ScrTogglePlayerControllable\(RPCParameters\* rpcParams\)',
          '// fix tahap 7: status bekukan dari server (dipakai untuk menyembunyikan/mengunci analog)\n'
          'bool g_bAcroServerFrozen = false;\n\n'
          '// 0.3.7\nvoid ScrTogglePlayerControllable(RPCParameters* rpcParams)', 'frozen global')
s = patch(s, r'(bsData\.Read\(byteControllable\);\s*)pGame->FindPlayerPed\(\)->TogglePlayerControllable\(byteControllable\);',
          'bsData.Read(byteControllable);\n\tg_bAcroServerFrozen = (byteControllable == 0);\n\n\tpGame->FindPlayerPed()->TogglePlayerControllable(byteControllable);',
          'frozen set')
wr(p, s)

p = S + '/game/hooks.cpp'
s = rd(p)
NEW_HELPER = '''extern bool g_bAcroServerFrozen;
static bool AcroTouchControlsLocked()
{
	static int s_last = -1;
	bool locked = false;
	const char* why = "normal";

	if (pNetGame && pNetGame->GetGameState() == GAMESTATE_CONNECTED)
	{
		CTextDrawPool* pTD = pNetGame->GetTextDrawPool();
		CPlayerPool* pPP = pNetGame->GetPlayerPool();
		if (g_bAcroServerFrozen) { locked = true; why = "server membekukan pemain"; }
		else if (pTD && pTD->GetState()) { locked = true; why = "SelectTextDraw aktif"; }
		else if (pTD && pPP && pPP->GetLocalPlayer() &&
				 !pPP->GetLocalPlayer()->IsSpawnedForInput() && pTD->HasAnyTextDraw()) { locked = true; why = "belum spawn"; }
	}

	if ((int)locked != s_last)
	{
		s_last = (int)locked;
		FLog("Kontrol game: %s (%s)", locked ? "DIKUNCI" : "dibuka", why);
	}
	return locked;
}
'''
s = patch(s, r'static bool AcroTouchControlsLocked\(\)\n\{.*?\n\}\n', NEW_HELPER, 'locked helper v2')
wr(p, s)
print('OK  kunci saat server membekukan pemain')

# ------------------------------------------------------------ 6. Widget bawaan GTA: penumpang + tinju
p = S + '/game/Widgets/WidgetGta.cpp'
s = rd(p)
REGISTRY = '''CWidgetGta* m_pWidgets[WidgetIDs::NUM_WIDGETS];

// fix tahap 7: daftar semua widget bawaan GTA berdasarkan nama (untuk menyembunyikan sesuai situasi)
struct AcroWidgetEntry { CWidgetGta* w; char name[24]; };
static AcroWidgetEntry g_acroWidgets[160];
static int g_acroWidgetCount = 0;

static void AcroRegisterWidget(const char* name, CWidgetGta* w)
{
    if (!name || !w || g_acroWidgetCount >= 160) return;
    g_acroWidgets[g_acroWidgetCount].w = w;
    strncpy(g_acroWidgets[g_acroWidgetCount].name, name, 23);
    g_acroWidgets[g_acroWidgetCount].name[23] = 0;
    g_acroWidgetCount++;
}

static bool AcroShouldHideWidget(CWidgetGta* w)
{
    if (!w || !pGame) return false;

    const char* n = nullptr;
    for (int i = 0; i < g_acroWidgetCount; i++)
        if (g_acroWidgets[i].w == w) { n = g_acroWidgets[i].name; break; }
    if (!n) return false;

    CPlayerPed* pPed = pGame->FindPlayerPed();
    if (!pPed || !pPed->m_pPed) return false;
    if (!pPed->IsInVehicle()) return false;

    // di dalam kendaraan: tombol tinju tidak dipakai
    if (!strcmp(n, "punch")) return true;

    // penumpang: tidak ikut menyetir
    if (pPed->m_pPed->IsAPassenger())
    {
        if (!strcmp(n, "hud_left") || !strcmp(n, "hud_right") ||
            !strcmp(n, "accelerate") || !strcmp(n, "brake") ||
            !strcmp(n, "handbrake") || !strcmp(n, "horn"))
        {
            static bool s_logged = false;
            if (!s_logged) { s_logged = true; FLog("Widget penumpang disembunyikan (contoh: %s)", n); }
            return true;
        }
    }
    return false;
}'''
s = patch(s, r'CWidgetGta\* m_pWidgets\[WidgetIDs::NUM_WIDGETS\];', REGISTRY, 'widget registry')
s = patch(s, r'void SetWidgetFromName\(const char\* name, CWidgetGta\* pWidget\)\s*\{',
          'void SetWidgetFromName(const char* name, CWidgetGta* pWidget)\n{\n    AcroRegisterWidget(name, pWidget);', 'register in ctor hook')
s = patch(s, r'eWidgetState ProcessFixedWidget\(CWidgetGta\* pWidget\)\s*\{',
          'eWidgetState ProcessFixedWidget(CWidgetGta* pWidget)\n{\n    if (AcroShouldHideWidget(pWidget)) return STATE_FIXED;\n', 'hide hook')
wr(p, s)
print('OK  widget penumpang / tinju')

# ------------------------------------------------------------ 7. Tombol G -> ikon penumpang
p = S + '/gui/samp_widgets/buttonpanel.cpp'
s = rd(p)
ICON = '''extern bool OpenButton;

/* Tombol panel berbentuk ikon (tanpa teks). kind 0 = naik sebagai penumpang */
class IconCButton : public CButton
{
public:
	IconCButton(float font_size, int kind) : CButton("MM", font_size), m_kind(kind) {}

	virtual void draw(ImGuiRenderer* renderer) override
	{
		if (OpenButton == false) return;

		ImVec2 a = absolutePosition();
		ImVec2 sz = size();
		renderer->drawGlassButton(a, ImVec2(a.x + sz.x, a.y + sz.y), UISettings::buttonColor(), focused());

		ImColor ic = focused() ? ImColor(0.07f, 0.07f, 0.07f) : ImColor(1.0f, 1.0f, 1.0f);
		float s = (sz.x < sz.y ? sz.x : sz.y) * 0.5f;
		float cx = a.x + sz.x * 0.5f;
		float cy = a.y + sz.y * 0.5f;

		if (m_kind == 0)
		{
			// penumpang: kepala + bahu di dalam siluet kursi
			float hr = s * 0.20f;
			renderer->drawRoundedRect(ImVec2(cx - hr, cy - s * 0.62f), ImVec2(cx + hr, cy - s * 0.22f), ic, hr, true);   // kepala
			renderer->drawRoundedRect(ImVec2(cx - s * 0.38f, cy - s * 0.12f), ImVec2(cx + s * 0.38f, cy + s * 0.42f), ic, s * 0.16f, true); // badan
			renderer->drawLine(ImVec2(cx - s * 0.62f, cy + s * 0.62f), ImVec2(cx + s * 0.62f, cy + s * 0.62f), ic, 2.0f); // dudukan
			renderer->drawLine(ImVec2(cx - s * 0.62f, cy - s * 0.30f), ImVec2(cx - s * 0.62f, cy + s * 0.62f), ic, 2.0f); // sandaran
		}
	}

private:
	int m_kind;
};

bool bNeedEnterVehicle = false;'''
G_PAT = r'CButton\*\s*m_bG\s*=\s*new\s+CButton\(\s*"G"\s*,[^;]*\);'
if len(re.findall(G_PAT, s)) == 1 and len(re.findall(r'bool bNeedEnterVehicle = false;', s)) == 1:
    s = patch(s, r'bool bNeedEnterVehicle = false;', ICON, 'icon class')
    s = patch(s, G_PAT,
              'CButton* m_bG = new IconCButton(UISettings::fontSize() / 2, 0); // ikon penumpang (dulu teks G)', 'G icon')
else:
    # tidak fatal: ikon G hanya kosmetik, jangan sampai menggagalkan build
    print('PERINGATAN: tombol G tidak ditemukan persis satu kali, ikon G dilewati. Baris terkait:')
    for i, line in enumerate(s.splitlines(), 1):
        if 'm_bG' in line or 'bNeedEnterVehicle' in line:
            print('   %d: %s' % (i, line.strip()[:140]))
wr(p, s)
print('OK  tombol G (lihat pesan di atas bila dilewati)')

# ------------------------------------------------------------ 8. Diagnosa: id RPC yang pertama kali masuk
p = S + '/vendor/raknet/RakPeer.cpp'
s = rd(p)
RPCLOG = '''rpcIndex = rpcMap.GetIndexFromFunctionName(uniqueIdentifier);
	{
		// diagnosa: catat tiap id RPC saat pertama kali masuk (terdaftar atau tidak)
		static bool s_seenRpc[256];
		unsigned int idRpc = (unsigned int)((uintptr_t)uniqueIdentifier & 0xFF);
		if (!s_seenRpc[idRpc])
		{
			s_seenRpc[idRpc] = true;
			extern void FLog(const char* fmt, ...);
			FLog("RPC id=%u pertama kali masuk, terdaftar=%d", idRpc, rpcIndex != UNDEFINED_RPC_INDEX ? 1 : 0);
		}
	}'''
s = patch(s, r'rpcIndex = rpcMap\.GetIndexFromFunctionName\(uniqueIdentifier\);', RPCLOG, 'rpc log')
wr(p, s)
print('OK  log id RPC')
print('SEMUA PATCH TAHAP 7 BERHASIL')

