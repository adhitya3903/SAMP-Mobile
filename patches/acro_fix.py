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
          'if (!BASS_Init(-1, 44100, BASS_DEVICE_3D, NULL, NULL) && BASS_ErrorGetCode() != 14) '
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

# ------------------------------------------------------------ 1b. AKAR crash mod: variabel output script 32-bit
# ScriptCommand(..."v") menulis uintptr (8 byte di arm64) ke alamat variabel. AddComponent memakai uint32_t (4 byte)
# -> stack canary rusak -> __stack_chk_fail -> abort (terbukti dari offset libsamp 0x147e28 / 0x182ea0 = AddComponent).
p = S + '/game/vehicle.cpp'
s = rd(p)
s = patch(s, r'uint32_t dwRet;(\s*ScriptCommand\(&add_car_component)', 'uintptr dwRet = 0;\\1'.replace('\\\\','\\'), 'AddComponent dwRet') if False else \
    patch_keep(s, r'uint32_t dwRet;(\s*ScriptCommand\(&add_car_component)', lambda m: 'uintptr dwRet = 0;' + m.group(1), 'AddComponent dwRet')
wr(p, s)
print('OK  AddComponent: variabel output 8 byte')

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

# ------------------------------------------------------------ 9. Desync: sirine, NOS, senjata, kendaraan telat tampil
# 9a. CVehicle::SirenEnabled() kondisinya TERBALIK (if(!m_pVehicle) return m_pVehicle->...): selalu false
#     -> sirine Android tidak pernah terkirim ke pemain lain.
p = S + '/game/vehicle.cpp'
s = rd(p)
s = patch(s, r'bool CVehicle::SirenEnabled\(\)\s*\{\s*if\(!m_pVehicle\)\s*return m_pVehicle->m_nVehicleFlags\.bSirenOrAlarm;\s*return false;\s*\}',
          'bool CVehicle::SirenEnabled()\n{\n\tif(m_pVehicle)\n\t\treturn m_pVehicle->m_nVehicleFlags.bSirenOrAlarm;\n\n\treturn false;\n}', 'SirenEnabled')
wr(p, s)

# 9b. Hook pad NOS / lihat kiri / lihat kanan: tidak ada return di jalur pemain remote (nilai sampah) dan
#     lihat kiri/kanan salah memakai tombol FIRE (menimpa tombol tembak/NOS lokal) -> NOS salah muncul / desync.
p = S + '/game/pad.cpp'
s = rd(p)
def pad_hook(name, getter, key_remote, key_local):
    global s
    pat = (r'(%s\s*\(uintptr_t thiz\)\s*\{)\s*if\(CWorld::PlayerInFocus\)\s*\{.*?\n\s*\}\s*else\s*\{.*?\n\s*\}\s*\}'
           % re.escape(name))
    new = (r'\1' + '\n    if(CWorld::PlayerInFocus)\n        return RemotePlayerKeys[byteCurPlayer].bKeys[ePadKeys::%s] ? 1 : 0;\n'
           '    LocalPlayerKeys.bKeys[ePadKeys::%s] = %s(thiz);\n    return LocalPlayerKeys.bKeys[ePadKeys::%s];\n}') % (key_remote, key_local, getter, key_local)
    s = patch_keep(s, pat, lambda m, n=new: m.expand(n), 'pad ' + name)
pad_hook('int CPad__GetNitroFired_hook', 'CPad__GetNitroFired', 'KEY_FIRE', 'KEY_FIRE')
pad_hook('uint32_t CPad__GetLookLeft_hook', 'CPad__GetLookLeft', 'KEY_LOOK_LEFT', 'KEY_LOOK_LEFT')
pad_hook('uint32_t CPad__GetLookRight_hook', 'CPad__GetLookRight', 'KEY_LOOK_RIGHT', 'KEY_LOOK_RIGHT')
wr(p, s)

# 9c. Senjata remote "mengisi peluru terus": status RELOADING di-set ulang tiap paket aim sync sehingga reload tak pernah selesai
p = S + '/net/remoteplayer.cpp'
s = rd(p)
s = patch(s, r'if \(paimSync->byteWeaponState == WEAPONSTATE_RELOADING\)\s*pwstWeapon->dwState = \(eWeaponState\)2;\s*// Reloading',
          'if (paimSync->byteWeaponState == WEAPONSTATE_RELOADING)\n\t{\n\t\tif (pwstWeapon->dwState != 2) pwstWeapon->dwState = (eWeaponState)2;\t// Reloading (sekali saja, jangan diulang tiap paket)\n\t}', 'reload loop')
wr(p, s)

# 9d. Kendaraan baru kadang tidak terlihat/tembus sampai pemain pindah interior: pasang ulang ke dunia (Remove+Add)
#     tak lama setelah dibuat dan sekali lagi beberapa detik kemudian (hanya bila kosong).
p = S + '/net/vehiclepool.h'
s = rd(p)
s = patch(s, r'void ProcessPendingMods\(uint32_t dwTick\);', 'void ProcessPendingMods(uint32_t dwTick);\n\tuint32_t m_dwRefreshTick[MAX_VEHICLES];\n\tuint8_t  m_byteRefreshStage[MAX_VEHICLES];', 'pool.h refresh')
wr(p, s)
p = S + '/net/vehiclepool.cpp'
s = rd(p)
s = patch_keep(s, r'(    // fix: mod \(velg, NOS, dll\), paintjob dan warna body diantre, dipasang aman oleh ProcessPendingMods\n)',
               lambda m: m.group(1) + '    m_dwRefreshTick[new_veh->VehicleID] = GetTickCount() + 700;\n    m_byteRefreshStage[new_veh->VehicleID] = 0;\n', 'refresh init')
s = patch_keep(s, r'(    int budget = 1;\n)',
          lambda m: m.group(1) + '''    for (VEHICLEID rid = 0; rid < MAX_VEHICLES; rid++)
    {
        if (!m_dwRefreshTick[rid] || dwTick < m_dwRefreshTick[rid]) continue;
        CVehicle* rv = m_pVehicles[rid];
        if (!rv || !m_bVehicleSlotState[rid] || !rv->m_pVehicle || !GamePool_Vehicle_GetAt(rv->m_dwGTAId)) { m_dwRefreshTick[rid] = 0; continue; }
        if (pGame->GetActiveInterior() != m_pendingMod[rid].interior) { m_dwRefreshTick[rid] = dwTick + 1000; continue; }
        if (!rv->m_pVehicle->m_pRwObject) { m_dwRefreshTick[rid] = dwTick + 500; continue; }
        if (!rv->IsOccupied()) { rv->m_pVehicle->Remove(); rv->m_pVehicle->Add(); }
        if (++m_byteRefreshStage[rid] >= 2) m_dwRefreshTick[rid] = 0; else m_dwRefreshTick[rid] = dwTick + 2500;
    }
''', 'refresh loop')
wr(p, s)

# 9e. Diagnosa: catat tiap RPC yang tidak terdaftar atau id 57 (mod kendaraan) setiap kali masuk (maks 60x)
p = S + '/vendor/raknet/RakPeer.cpp'
s = rd(p)
s = patch_keep(s, r'(\t\tstatic bool s_seenRpc\[256\];\n)',
          lambda m: m.group(1) + '''		static int s_rpcCount;
		{
			unsigned int idChk = (unsigned int)((uintptr_t)uniqueIdentifier & 0xFF);
			if ((rpcIndex == UNDEFINED_RPC_INDEX || idChk == 57) && s_rpcCount < 60)
			{
				s_rpcCount++;
				extern void FLog(const char* fmt, ...);
				FLog("RPC masuk id=%u terdaftar=%d (kemungkinan mod kendaraan runtime)", idChk, rpcIndex != UNDEFINED_RPC_INDEX ? 1 : 0);
			}
		}
''', 'rpc diag 2')
wr(p, s)
print('OK  desync: sirine, NOS, reload, kendaraan telat tampil, diagnosa RPC')

# 9f. Inisialisasi array antrean mod/refresh di konstruktor pool (kalau tidak, isi sampah -> proses acak)
p = S + '/net/vehiclepool.cpp'
s = rd(p)
s = patch_keep(s, r'(CVehiclePool::CVehiclePool\(\)\s*\{\s*for \(int i = 0; i < MAX_VEHICLES; i\+\+\)\s*\{\s*m_pVehicles\[i\] = nullptr;)',
               lambda m: m.group(1) + '\n        memset(&m_pendingMod[i], 0, sizeof(m_pendingMod[i]));\n        m_dwRefreshTick[i] = 0;\n        m_byteRefreshStage[i] = 0;', 'pool ctor init')
wr(p, s)
print('OK  init array pool')


# ------------------------------------------------------------ 10. Spawn/pilih karakter tidak bisa disentuh (server roleplay)
# Akar masalah (dari log): SetSelectState(false) SELALU mengirim ClickTextDraw(0xFFFF) ke server = "pemain menekan ESC".
# Saat server memanggil CancelSelectTextDraw, client membalas "ESC", lalu skrip roleplay merespons (pilih ulang / batal lagi)
# -> perulangan enable=0/enable=1 ratusan kali; di sela-selanya mode pilih mati sehingga sentuhan Spawn hilang,
# dan tiap batal juga membuka kunci pemain yang dibekukan server. SA-MP asli hanya mengirim klik saat pemain menekan ESC.
p = S + '/net/textdrawpool.h'
s = rd(p)
s = patch(s, r'void SetSelectState\(bool bState, uint32_t dwColor = 0\);',
          'void SetSelectState(bool bState, uint32_t dwColor = 0, bool bNotifyServer = true);', 'select h')
wr(p, s)

p = S + '/net/textdrawpool.cpp'
s = rd(p)
s = patch(s, r'void CTextDrawPool::SetSelectState\(bool bState, uint32_t dwColor\)\s*\{',
          'extern bool g_bAcroServerFrozen;\n\nvoid CTextDrawPool::SetSelectState(bool bState, uint32_t dwColor, bool bNotifyServer)\n{', 'select cpp sig')
s = patch(s, r'pGame->DisplayHUD\(true\);\s*FLog\("SelectTextDraw: nonaktif"\);\s*pGame->FindPlayerPed\(\)->TogglePlayerControllable\(true\);\s*SendClick\(\);',
          'pGame->DisplayHUD(true);\n        FLog("SelectTextDraw: nonaktif (dari %s)", bNotifyServer ? "pemain" : "server");\n        if (!g_bAcroServerFrozen) pGame->FindPlayerPed()->TogglePlayerControllable(true);\n\n        // hanya kirim "ESC" bila pemain yang menutup (tombol ESC), bukan saat server yang membatalkan\n        if (bNotifyServer) SendClick();',
          'select cpp body')
wr(p, s)

p = S + '/net/scriptrpc.cpp'
s = rd(p)
s = patch(s, r'pNetGame->GetTextDrawPool\(\)->SetSelectState\(bEnable \? true : false, dwColor\);',
          'pNetGame->GetTextDrawPool()->SetSelectState(bEnable ? true : false, dwColor, false); // dari server: jangan balas ESC', 'select rpc')
wr(p, s)
print('OK  Spawn: batal dari server tidak lagi membalas ESC / membuka kunci')


# ------------------------------------------------------------ 11. Tombol panel tersembunyi masih menerima sentuhan + tombol penumpang baru
# 11a. Saat layar pilih karakter/spawn, tombol panel (TAB, ESC, ...) walau tidak terlihat masih menangkap sentuhan,
#      sehingga menimpa nama karakter / tombol Spawn yang berada di area yang sama. Sekarang UI diabaikan di layar itu.
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch_keep(s, r'(\tif \(\(int\)locked != s_last\)\s*\{.*?\n\t\}\n\treturn locked;\n\}\n)',
               lambda m: m.group(1) + '''
// true = layar pilih karakter / spawn / SelectTextDraw: UI panel tidak boleh menerima sentuhan
bool AcroSelectScreenActive()
{
	if (!pNetGame || pNetGame->GetGameState() != GAMESTATE_CONNECTED) return false;
	CTextDrawPool* pTD = pNetGame->GetTextDrawPool();
	CPlayerPool* pPP = pNetGame->GetPlayerPool();
	if (pTD && pTD->GetState()) return true;
	if (pTD && pPP && pPP->GetLocalPlayer() && !pPP->GetLocalPlayer()->IsSpawnedForInput() && pTD->HasAnyTextDraw()) return true;
	return false;
}
''', 'AcroSelectScreenActive')
wr(p, s)

p = S + '/gui/gui.cpp'
s = rd(p)
s = patch_keep(s, r'(\tWidget::touchEvent\(pos, type\);\n\}\n\nenum eTouchType)',
               lambda m: '\t{ extern bool AcroSelectScreenActive(); if (AcroSelectScreenActive()) return; }\n' + m.group(1), 'gui touch block')
s = patch_keep(s, r'(\tm_voiceButton = new VoiceButton\(\);)',
               lambda m: '\t{ extern Widget* CreatePassengerButton(); this->addChild(CreatePassengerButton()); }\n' + m.group(1), 'gui add passenger')
wr(p, s)

# 11b. Tombol penumpang: dihapus dari deretan >> dan dipindah jadi tombol sentuh di samping tombol "naik pengemudi"
p = S + '/gui/samp_widgets/buttonpanel.cpp'
s = rd(p)
s = patch_keep(s, r'(\tthis->addChild\(m_bG\);)', lambda m: '\t// tombol penumpang dipindah ke samping tombol naik kendaraan (PassengerButton)', 'panel remove G')
s = patch_keep(s, r'(bool bNeedEnterVehicle = false;)',
               lambda m: '''bool AcroSelectScreenActive();
extern bool bNeedEnterVehicle;
extern CGame* pGame;

/* Tombol sentuh "naik sebagai penumpang": muncul di sebelah kiri tombol naik pengemudi bila ada kendaraan dekat */
class PassengerButton : public Widget
{
public:
	PassengerButton()
	{
		ImVec2 d = ImGui::GetIO().DisplaySize;
		float r = d.y * 0.066f;
		setFixedSize(ImVec2(r * 2.0f, r * 2.0f));
		setPosition(ImVec2(d.x * 0.880f - r, d.y * 0.575f - r));
		m_cacheTick = 0; m_cacheShow = false;
	}

	bool shouldShow()
	{
		if (!pNetGame || pNetGame->GetGameState() != GAMESTATE_CONNECTED) return false;
		if (AcroSelectScreenActive()) return false;
		if (pUI && (pUI->keyboard()->visible() || pUI->dialog()->visible() || pUI->playertablist()->visible())) return false;
		CPlayerPool* pp = pNetGame->GetPlayerPool();
		if (!pp || !pp->GetLocalPlayer() || !pp->GetLocalPlayer()->IsSpawnedForInput()) return false;
		CPlayerPed* ped = pGame ? pGame->FindPlayerPed() : nullptr;
		if (!ped || !ped->m_pPed || ped->IsInVehicle()) return false;

		uint32_t now = GetTickCount();
		if (now - m_cacheTick > 200)
		{
			m_cacheTick = now;
			m_cacheShow = false;
			CVehiclePool* vp = pNetGame->GetVehiclePool();
			if (vp)
			{
				CVehicle* v = vp->GetAt(vp->FindNearestToLocalPlayerPed());
				if (v && v->m_pVehicle && v->m_pVehicle->GetDistanceFromLocalPlayerPed() < 8.0f) m_cacheShow = true;
			}
		}
		return m_cacheShow;
	}

	virtual void draw(ImGuiRenderer* renderer) override
	{
		if (!shouldShow()) return;
		ImVec2 a = absolutePosition();
		ImVec2 sz = size();
		renderer->drawGlassButton(a, ImVec2(a.x + sz.x, a.y + sz.y), UISettings::buttonColor(), focused());

		ImColor ic = focused() ? ImColor(0.07f, 0.07f, 0.07f) : ImColor(1.0f, 1.0f, 1.0f);
		float s = (sz.x < sz.y ? sz.x : sz.y) * 0.34f;
		float cx = a.x + sz.x * 0.5f;
		float cy = a.y + sz.y * 0.5f;
		// siluet kursi dengan orang duduk (penumpang)
		float hr = s * 0.20f;
		renderer->drawRoundedRect(ImVec2(cx - hr, cy - s * 0.66f), ImVec2(cx + hr, cy - s * 0.26f), ic, hr, true);
		renderer->drawRoundedRect(ImVec2(cx - s * 0.36f, cy - s * 0.16f), ImVec2(cx + s * 0.36f, cy + s * 0.40f), ic, s * 0.16f, true);
		renderer->drawLine(ImVec2(cx - s * 0.64f, cy + s * 0.64f), ImVec2(cx + s * 0.64f, cy + s * 0.64f), ic, 3.0f);
		renderer->drawLine(ImVec2(cx - s * 0.64f, cy - s * 0.34f), ImVec2(cx - s * 0.64f, cy + s * 0.64f), ic, 3.0f);
	}

	virtual void touchEvent(const ImVec2& pos, TouchType type) override
	{
		if (!shouldShow()) return;
		Widget::touchEvent(pos, type);
	}

	virtual void touchPopEvent() override { bNeedEnterVehicle = true; }

private:
	uint32_t m_cacheTick;
	bool m_cacheShow;
};

Widget* CreatePassengerButton() { return new PassengerButton(); }

bool bNeedEnterVehicle = false;''', 'panel passenger class')
wr(p, s)

# 11c. Diagnosa kendaraan "ghaib": catat bila objek kendaraan hilang dari pool game padahal masih aktif di server
p = S + '/net/vehiclepool.cpp'
s = rd(p)
s = patch_keep(s, r'(    int budget = 1;\n)',
               lambda m: m.group(1) + '''    {
        static bool s_gone[MAX_VEHICLES];
        for (VEHICLEID gid = 0; gid < MAX_VEHICLES; gid++)
        {
            CVehicle* gv = m_pVehicles[gid];
            bool active = gv && m_bVehicleSlotState[gid] && gv->m_pVehicle;
            bool gone = active && !GamePool_Vehicle_GetAt(gv->m_dwGTAId);
            if (gone && !s_gone[gid]) FLog("Kendaraan %d hilang dari pool game padahal masih aktif (desync 'ghaib')", (int)gid);
            s_gone[gid] = gone;
        }
    }
''', 'ghost diag')
wr(p, s)
print('OK  tombol panel tak menerima sentuhan di layar spawn, tombol penumpang baru, diagnosa kendaraan ghaib')


# ======================================================================== BAGIAN 12 (perbaikan 21 Nov)
# 12a. Tombol panel (<< TAB ESC ALT H Y N F 2) tidak boleh menerima sentuhan saat panel ditutup,
#      dan tombol ">>" tidak menerima sentuhan saat panel terbuka (dulu hanya "tidak digambar", sentuhan tetap masuk)
p = S + '/gui/widgets/button.h'
s = rd(p)
s = patch_keep(s, r'(class (?:CButton|OButton) : public Widget\n\{.*?\tvirtual void touchPopEvent\(\) override;\n)',
               lambda m: m.group(1) + '\tvirtual void touchEvent(const ImVec2& pos, TouchType type) override;\n',
               'button.h touchEvent', count=2)
wr(p, s)
p = S + '/gui/widgets/button.cpp'
s = rd(p)
s += """

// fix: panel tertutup -> tombol di dalamnya tidak boleh bisa dipencet (walau tidak tergambar)
void CButton::touchEvent(const ImVec2& pos, TouchType type)
{
	if (OpenButton == false) return;
	Widget::touchEvent(pos, type);
}

// fix: panel terbuka -> tombol ">>" sudah pindah keluar layar, jangan terima sentuhan
void OButton::touchEvent(const ImVec2& pos, TouchType type)
{
	if (OpenButton == true) return;
	Widget::touchEvent(pos, type);
}
"""
wr(p, s)

# 12b. Kunci kontrol "belum spawn" hanya saat layar pilih-karakter (dialog Spawn << >>) benar-benar tampil.
#      Dulu: tidak spawn + ada textdraw apa pun -> terkunci selamanya (login selesai tapi tidak bisa menyentuh apa pun).
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'else if \(pTD && pPP && pPP->GetLocalPlayer\(\) &&\s*!pPP->GetLocalPlayer\(\)->IsSpawnedForInput\(\) && pTD->HasAnyTextDraw\(\)\) \{ locked = true; why = "belum spawn"; \}',
          'else if (pPP && pPP->GetLocalPlayer() && !pPP->GetLocalPlayer()->IsSpawnedForInput() &&\n'
          '\t\t\t\t pUI && pUI->spawn() && pUI->spawn()->visible()) { locked = true; why = "layar pilih karakter"; }',
          'lock belum spawn')
s = patch(s, r'if \(pTD && pPP && pPP->GetLocalPlayer\(\) && !pPP->GetLocalPlayer\(\)->IsSpawnedForInput\(\) && pTD->HasAnyTextDraw\(\)\) return true;',
          'if (pPP && pPP->GetLocalPlayer() && !pPP->GetLocalPlayer()->IsSpawnedForInput() &&\n'
          '\t\tpUI && pUI->spawn() && pUI->spawn()->visible()) return true;',
          'select screen active')
wr(p, s)

# 12c. Widget bawaan GTA (naik mobil, lari, gas, rem): sinkronkan status enable.
#      Dulu kita memaksa SetEnabled(false) lalu berhenti, sehingga saat kondisi normal kembali widget tetap
#      "mati" (tidak tergambar) tapi Update jalan lagi -> tombol tak terlihat namun bisa dipencet, atau sebaliknya.
p = S + '/game/Widgets/WidgetGta.cpp'
s = rd(p)
s = patch(s, r'struct AcroWidgetEntry \{ CWidgetGta\* w; char name\[24\]; \};',
          'struct AcroWidgetEntry { CWidgetGta* w; char name[24]; bool intended; bool forced; };', 'entry struct')
s = patch(s, r'(    g_acroWidgets\[g_acroWidgetCount\]\.w = w;\n)',
          '    g_acroWidgets[g_acroWidgetCount].w = w;\n    g_acroWidgets[g_acroWidgetCount].intended = false;\n    g_acroWidgets[g_acroWidgetCount].forced = false;\n',
          'entry init')
s = patch(s, r'(static bool AcroShouldHideWidget\(CWidgetGta\* w\))',
          'static AcroWidgetEntry* AcroFindWidget(CWidgetGta* w)\n{\n    for (int i = 0; i < g_acroWidgetCount; i++)\n        if (g_acroWidgets[i].w == w) return &g_acroWidgets[i];\n    return nullptr;\n}\n\n'
          'static bool AcroShouldHideWidget(CWidgetGta* w)', 'find helper')
s = patch(s, r'void CWidget__SetEnabled_hook\(CWidgetGta\* pWidget, bool bEnabled\)\n\{\n    if\(pNetGame\)\n    \{\n        switch\(ProcessFixedWidget\(pWidget\)\)\n        \{\n            case STATE_NONE: break;\n            case STATE_FIXED:\n                bEnabled = false;\n                break;\n        \}\n    \}\n',
          'void CWidget__SetEnabled_hook(CWidgetGta* pWidget, bool bEnabled)\n{\n    AcroWidgetEntry* e = AcroFindWidget(pWidget);\n    if (e) { e->intended = bEnabled; e->forced = false; }\n    if(pNetGame)\n    {\n        switch(ProcessFixedWidget(pWidget))\n        {\n            case STATE_NONE: break;\n            case STATE_FIXED:\n                bEnabled = false;\n                if (e) e->forced = true;\n                break;\n        }\n    }\n',
          'SetEnabled hook')
s = patch(s, r'void CWidgetButton__Update_hook\(CWidgetButton\* thiz\) \{\n    if\(pNetGame\)\n    \{\n        switch\(ProcessFixedWidget\(thiz\)\)\n        \{\n            case STATE_NONE: break;\n            case STATE_FIXED: return;\n        \}\n    \}\n',
          'void CWidgetButton__Update_hook(CWidgetButton* thiz) {\n    if(pNetGame)\n    {\n        AcroWidgetEntry* e = AcroFindWidget(thiz);\n        switch(ProcessFixedWidget(thiz))\n        {\n            case STATE_NONE:\n                if (e && e->forced) { e->forced = false; CWidget__SetEnabled(thiz, e->intended); }\n                break;\n            case STATE_FIXED:\n                if (e) { e->forced = true; CWidget__SetEnabled(thiz, false); }\n                return;\n        }\n    }\n',
          'Update hook')
wr(p, s)
print('OK  panel tak bisa disentuh saat tertutup, kunci spawn hanya di layar pilih karakter, sinkron widget GTA')

# 12d. BUG dari tahap 11: layar pilih karakter memblokir SEMUA sentuhan ke UI, termasuk tombol << Spawn >> milik dialog Spawn
#      sendiri. Sekarang saat layar itu aktif, hanya dialog Spawn yang boleh menerima sentuhan (panel dll tetap diblokir).
p = S + '/gui/gui.cpp'
s = rd(p)
s = patch(s, r'\{ extern bool AcroSelectScreenActive\(\); if \(AcroSelectScreenActive\(\)\) return; \}',
          '{ extern bool AcroSelectScreenActive(); if (AcroSelectScreenActive()) { if (m_spawn && m_spawn->visible()) m_spawn->touchEvent(pos, type); return; } }',
          'spawn dialog tetap menerima sentuhan')
wr(p, s)
print('OK  tombol Spawn << >> bisa disentuh lagi')

# ======================================================================== BAGIAN 13 (22 Nov)
# 13a. Tekstur "setengah"/kosong + "rled error 3": ukuran sumber RLE diambil dari OS_FileRead TERAKHIR (variabel global,
#      ditimpa thread lain / sudah di-nol-kan), sehingga dekompresi berhenti di tengah (ikon separo) atau tidak jalan sama
#      sekali (ikon hilang). Sekarang: variabel per-thread, dan batas sumber hanya saran (dilewati -> lanjut seperti kode asli GTA).
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'static uint32_t dwRLEDecompressSourceSize = 0;',
          'static thread_local uint32_t dwRLEDecompressSourceSize = 0;', 'rle thread_local')
s = patch(s, r'void RLEDecompress_hook\(uint8_t\* pDest.*?\n\}\n', """void RLEDecompress_hook(uint8_t* pDest, size_t uiDestSize, const uint8_t* pSrc, size_t uiSegSize, uint32_t uiEscape) {

    if (!pDest || !pSrc || uiDestSize == 0 || uiSegSize == 0) return;

    size_t srcLimit = dwRLEDecompressSourceSize; // 0 = tidak diketahui
    const uint8_t* pTempSrc = pSrc;
    const uint8_t* const pEndOfDest = pDest + uiDestSize;
    static int s_loose = 0;

    while (pDest < pEndOfDest) {
        if (srcLimit && (size_t)(pTempSrc - pSrc) >= srcLimit) {
            // ukuran sumber yang tercatat lebih kecil dari datanya (catatan basi): lanjut seperti kode asli
            if (s_loose++ < 5) FLog("RLE: batas sumber %u terlewati, dilanjutkan tanpa batas", (unsigned)srcLimit);
            srcLimit = 0;
        }
        if (*pTempSrc == uiEscape) {
            uint8_t ucCurSeg = pTempSrc[1];
            while (ucCurSeg--) {
                if (pDest + uiSegSize > pEndOfDest) { dwRLEDecompressSourceSize = 0; return; } // jangan menulis di luar buffer tujuan
                memcpy(pDest, pTempSrc + 2, uiSegSize);
                pDest += uiSegSize;
            }
            pTempSrc += 2 + uiSegSize;
        } else {
            size_t n = (size_t)(pEndOfDest - pDest);
            if (n > uiSegSize) n = uiSegSize;
            memcpy(pDest, pTempSrc, n);
            pDest += uiSegSize;
            pTempSrc += uiSegSize;
        }
    }

    dwRLEDecompressSourceSize = 0;
}
""", 'rle hook')

# 13c. Pemain dibekukan server (misal checkpoint side job bus) TIDAK boleh mengunci semua tombol:
#      skrip server sering menunggu tombol (Y/N/ALT/F). Kunci layar hanya untuk SelectTextDraw / layar pilih karakter.
s = patch(s, r'if \(g_bAcroServerFrozen\) \{ locked = true; why = "server membekukan pemain"; \}\s*else if \(pTD && pTD->GetState\(\)\)',
          'if (pTD && pTD->GetState())', 'frozen tidak mengunci')

# 13e. Profil frame: tiap 5 detik catat rata-rata ms per frame, ms HUD+textdraw, ms UI (bahan untuk optimasi FPS)
s = patch(s, r'void Render2dStuff\(\)\n\{\n',
          '#include <chrono>\nvoid Render2dStuff()\n{\n    auto acroT0 = std::chrono::steady_clock::now();\n', 'profil awal')
s = patch(s, r'if \(pUI\) pUI->render\(\);\n\}\n\n/\* =+ \*/\n\nint \(\*CRadar__SetCoordBlip\)', """auto acroT1 = std::chrono::steady_clock::now();
    if (pUI) pUI->render();
    {
        auto acroT2 = std::chrono::steady_clock::now();
        static double sHud = 0, sUi = 0; static int sN = 0;
        static auto sWin = acroT2;
        sHud += std::chrono::duration<double, std::milli>(acroT1 - acroT0).count();
        sUi  += std::chrono::duration<double, std::milli>(acroT2 - acroT1).count();
        sN++;
        double win = std::chrono::duration<double, std::milli>(acroT2 - sWin).count();
        if (win >= 5000.0)
        {
            FLog("PROFIL 5dtk: %d frame, %.1f ms/frame (%.0f FPS), HUD+textdraw %.2f ms, UI %.2f ms",
                 sN, win / sN, sN * 1000.0 / win, sHud / sN, sUi / sN);
            sHud = sUi = 0; sN = 0; sWin = acroT2;
        }
    }
}

/* =============================================================================== */

int (*CRadar__SetCoordBlip)""", 'profil akhir')
wr(p, s)

# 13b. Cahaya lampu jalan yang menempel di aspal (static shadow) ikut dimatikan oleh RET lama -> aktifkan lagi.
p = S + '/game/patches.cpp'
s = rd(p)
s = patch(s, r'\tCHook::RET\("_ZN8CShadows19RenderStaticShadowsEb"\);[^\n]*\n',
          '\t// CShadows::RenderStaticShadows = cahaya lampu jalan di aspal; default MATI (FPS); nyalakan lewat settings.ini [gui] StaticShadows=1\n\tif (pSettings && !pSettings->Get().bStaticShadows) CHook::RET("_ZN8CShadows19RenderStaticShadowsEb");\n',
          'static shadows toggle')
wr(p, s)

p = S + '/settings.h'
s = rd(p)
s = patch_keep(s, r'(\tbool bPassengerUseTexture;)', lambda m: '\tbool bStaticShadows;\n' + m.group(1), 'settings.h StaticShadows')
wr(p, s)
p = S + '/settings.cpp'
s = rd(p)
s = patch_keep(s, r'(\tm_Settings\.bPassengerUseTexture = )', lambda m: '\tm_Settings.bStaticShadows = reader.GetBoolean("gui", "StaticShadows", true);\n' + m.group(1), 'settings.cpp StaticShadows')
wr(p, s)

# 15. Tombol voice digeser ~1% ke kiri (500 -> 493.6 dari lebar basis 640)
p = S + '/gui/uisettings.cpp'
s = rd(p)
s = patch(s, r'ImVec2\(500\.0f, 180\.0f', 'ImVec2(493.6f, 180.0f', 'voice 1% kiri')
wr(p, s)

# 15b. Log damage untuk diagnosa tonjok/tembak PC <-> Android
p = S + '/net/localplayer.cpp'
s = rd(p)
s = patch_keep(s, r'(void CLocalPlayer::SendTakeDamageEvent\([^)]*\)\s*\{\n)', lambda m: m.group(1) + '\tFLog("DAMAGE kirim TAKE dari=%d faktor=%.2f senjata=%d bagian=%d", PlayerID, fDamageFactor, weaponType, pedPieceType);\n', 'log take')
s = patch_keep(s, r'(void CLocalPlayer::SendGiveDamageEvent\([^)]*\)\s*\{\n)', lambda m: m.group(1) + '\tFLog("DAMAGE kirim GIVE ke=%d faktor=%.2f senjata=%d bagian=%d", PlayerID, fDamageFactor, weaponType, pedPieceType);\n', 'log give')
wr(p, s)

# 13d. Tombol penumpang memakai tekstur "PassengerButton" dari mobile.txt bila ada (cadangan: gambar vektor)
p = S + '/gui/samp_widgets/buttonpanel.cpp'
s = rd(p)
s = patch(s, r'm_cacheTick = 0; m_cacheShow = false;',
          'm_cacheTick = 0; m_cacheShow = false; m_tex = nullptr; m_texTried = false;', 'pb ctor')
s = patch(s, r'if \(!shouldShow\(\)\) return;\s*ImVec2 a = absolutePosition\(\);', """if (!shouldShow()) return;
		if (!m_texTried) { m_texTried = true; m_tex = (RwTexture*)CUtil::LoadTextureFromDB("mobile", "PassengerButton"); }
		if (m_tex && m_tex->raster)
		{
			ImVec2 ta = absolutePosition();
			renderer->drawImage(ta, ta + size(), (ImTextureID)m_tex->raster);
			return;
		}
		ImVec2 a = absolutePosition();""", 'pb draw')
s = patch(s, r'uint32_t m_cacheTick;\s*bool m_cacheShow;\s*\};',
          'uint32_t m_cacheTick;\n\tbool m_cacheShow;\n\tRwTexture* m_tex;\n\tbool m_texTried;\n};', 'pb members')
wr(p, s)
print('OK  tekstur RLE tidak terpotong, lampu jalan aktif, beku server tidak kunci tombol, tombol penumpang pakai tekstur, profil FPS')

# ======================================================================== BAGIAN 14 (22 Nov, dari log baru)
# 14a. Tombol bawaan GTA nyangkut (lari saat di mobil, panah setir saat jalan kaki). Penyebab: widget "lari" tidak punya nama
#      (nama kosong) sehingga aturan lama tidak pernah kena, dan widget yang Update-nya dilewati membeku di keadaan terakhir.
#      Sekarang dikenali dari POSISI (lari menimpa tombol gas; panah setir ada di kiri-bawah), dan saat disembunyikan
#      status + alpha dipaksa mati lalu dipulihkan persis saat boleh tampil lagi.
p = S + '/game/Widgets/WidgetGta.cpp'
s = rd(p)
s = patch(s, r'bool intended; bool forced; \};', 'bool intended; bool forced; uint8_t savedAlpha; bool alphaSaved; };', 'entry alpha')
s = patch(s, r'(    g_acroWidgets\[g_acroWidgetCount\]\.forced = false;\n)',
          '    g_acroWidgets[g_acroWidgetCount].forced = false;\n    g_acroWidgets[g_acroWidgetCount].savedAlpha = 255;\n    g_acroWidgets[g_acroWidgetCount].alphaSaved = false;\n', 'entry alpha init')
s = patch(s, r'    CPlayerPed\* pPed = pGame->FindPlayerPed\(\);\n    if \(!pPed \|\| !pPed->m_pPed\) return false;\n    if \(!pPed->IsInVehicle\(\)\) return false;\n',
"""    CPlayerPed* pPed = pGame->FindPlayerPed();
    if (!pPed || !pPed->m_pPed) return false;
    bool inVeh = pPed->IsInVehicle();

    CWidgetGta* acc = m_pWidgets[WidgetIDs::WIDGET_ACCELERATE];
    CWidgetGta* brk = m_pWidgets[WidgetIDs::WIDGET_BRAKE];
    if (acc && brk && w != acc && w != brk && w->m_RectScreen.right > w->m_RectScreen.left)
    {
        float aw = acc->m_RectScreen.right - acc->m_RectScreen.left;
        if (aw < 0) aw = -aw;
        float ax = (acc->m_RectScreen.left + acc->m_RectScreen.right) * 0.5f;
        float ay = (acc->m_RectScreen.top + acc->m_RectScreen.bottom) * 0.5f;
        float bx = (brk->m_RectScreen.left + brk->m_RectScreen.right) * 0.5f;
        float cx = (w->m_RectScreen.left + w->m_RectScreen.right) * 0.5f;
        float cy = (w->m_RectScreen.top + w->m_RectScreen.bottom) * 0.5f;
        if (aw > 1.0f)
        {
            // tombol lari/loncat yang menimpa tombol gas -> sembunyikan saat di kendaraan
            if (inVeh && fabsf(cx - ax) < aw * 0.35f && fabsf(cy - ay) < aw * 0.35f) return true;
            // panah setir kiri/kanan (kiri-bawah) -> sembunyikan saat jalan kaki
            if (!inVeh && (!strcmp(n, "hud_left") || !strcmp(n, "hud_right")) &&
                cx < bx - aw * 0.5f && fabsf(cy - ay) < aw * 0.8f) return true;
        }
    }
    if (!inVeh) return false;
""", 'hide rules posisi')
s = patch(s, r'            case STATE_NONE:\n                if \(e && e->forced\) \{ e->forced = false; CWidget__SetEnabled\(thiz, e->intended\); \}\n                break;\n            case STATE_FIXED:\n                if \(e\) \{ e->forced = true; CWidget__SetEnabled\(thiz, false\); \}\n                return;\n',
"""            case STATE_NONE:
                if (e && e->forced)
                {
                    e->forced = false;
                    if (e->alphaSaved) { thiz->m_Color.a = e->savedAlpha; e->alphaSaved = false; }
                    CWidget__SetEnabled(thiz, e->intended);
                }
                break;
            case STATE_FIXED:
                if (e)
                {
                    if (!e->alphaSaved && thiz->m_Color.a != 0) { e->savedAlpha = thiz->m_Color.a; e->alphaSaved = true; }
                    e->forced = true;
                    thiz->m_bEnabled = false;
                    thiz->m_bCachedEnabled = false;
                    thiz->m_Color.a = 0;
                }
                return;
""", 'update hook paksa mati')
wr(p, s)

# 14b. Profil lebih rinci: waktu NetGame::Process (jaringan + pemain + kendaraan) per frame
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'#include <chrono>\nvoid Render2dStuff\(\)',
          '#include <chrono>\ndouble g_acroProfNet = 0, g_acroProfPl = 0, g_acroProfVeh = 0;\nvoid Render2dStuff()', 'profil global')
s = patch(s, r'FLog\("PROFIL 5dtk:.*?sWin = acroT2;',
"""FLog("PROFIL 5dtk: %d frame, %.1f ms/frame (%.0f FPS), HUD+textdraw %.2f, UI %.2f, NET %.2f [pemain %.2f, kendaraan %.2f] ms",
                 sN, win / sN, sN * 1000.0 / win, sHud / sN, sUi / sN, g_acroProfNet / sN, g_acroProfPl / sN, g_acroProfVeh / sN);
            FLog("STREAM: terpakai %zu MB / tersedia %zu MB, kendaraan dimuat maks %u", (size_t)(CStreaming::ms_memoryUsed >> 20), (size_t)(CStreaming::ms_memoryAvailable >> 20), (unsigned)CStreaming::desiredNumVehiclesLoaded);
            sHud = sUi = 0; sN = 0; sWin = acroT2; g_acroProfNet = g_acroProfPl = g_acroProfVeh = 0;""", 'profil print')
wr(p, s)

p = S + '/main.cpp'
s = rd(p)
s = patch(s, r'if \(pNetGame\) \{\s*pNetGame->Process\(\);\s*\}',
"""if (pNetGame) {
		extern double g_acroProfNet;
		auto acroN0 = std::chrono::steady_clock::now();
		pNetGame->Process();
		g_acroProfNet += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - acroN0).count();
	}""", 'profil net main')
s = (s[:3] + '#include <chrono>\n' + s[3:]) if s.startswith('\xef\xbb\xbf') else ('#include <chrono>\n' + s)
wr(p, s)

p = S + '/net/netgame.cpp'
s = rd(p)
s = patch(s, r'\tif \(GetPlayerPool\(\)\) \{\s*GetPlayerPool\(\)->Process\(\);\s*\}\s*if\(GetVehiclePool\(\)\) \{\s*GetVehiclePool\(\)->Process\(\);\s*\}',
"""	extern double g_acroProfPl, g_acroProfVeh;
	if (GetPlayerPool()) {
		auto acroP0 = std::chrono::steady_clock::now();
		GetPlayerPool()->Process();
		g_acroProfPl += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - acroP0).count();
	}

	if(GetVehiclePool()) {
		auto acroV0 = std::chrono::steady_clock::now();
		GetVehiclePool()->Process();
		g_acroProfVeh += std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - acroV0).count();
	}""", 'profil pools')
s = (s[:3] + '#include <chrono>\n' + s[3:]) if s.startswith('\xef\xbb\xbf') else ('#include <chrono>\n' + s)
wr(p, s)

# 14c. Diagnosa freeze: catat tiap perintah bekukan/lepas dari server beserta status di kendaraan
p = S + '/net/scriptrpc.cpp'
s = rd(p)
s = patch(s, r'(\tg_bAcroServerFrozen = \(byteControllable == 0\);\n)',
          '\tg_bAcroServerFrozen = (byteControllable == 0);\n\tFLog("Server %s pemain (di kendaraan=%d)", byteControllable ? "MELEPAS beku" : "MEMBEKUKAN", (pGame && pGame->FindPlayerPed() && pGame->FindPlayerPed()->IsInVehicle()) ? 1 : 0);\n',
          'freeze diag')
wr(p, s)
print('OK  tombol bawaan nyangkut (posisi + alpha), profil NET/pemain/kendaraan, diagnosa freeze')

# 16. Crash 32-bit (Redmi 6A): CSprite2d::Draw(UV) dipanggil lewat offset hard-code 0x1974EC yang bukan kode
#     (SIGSEGV pc=libGTASA+0x1974EC, pemanggil DrawTextureUV <- CTextDraw sprite). Ganti dengan gambar sendiri.
p = S + '/game/util.cpp'
s = rd(p)
s = patch(s, r'void DrawTextureUV\(uintptr_t texture, CRect\* rect, uint32_t dwColor, float \*uv\)\s*\{.*?\n\}\n',
"""void DrawTextureUV(uintptr_t texture, CRect* rect, uint32_t dwColor, float *uv)
{
	if (!texture || !rect || !uv) return;

	RwRenderStateSet(rwRENDERSTATETEXTUREFILTER, (void*)rwFILTERLINEAR);
#if VER_x32
	// 32-bit: jangan pakai alamat hard-code, gambar sendiri lewat CSprite2d buatan modul ini
	alignas(CSprite2d) static char s_acroSpriteBuf[sizeof(CSprite2d)];
	CSprite2d* spr = reinterpret_cast<CSprite2d*>(s_acroSpriteBuf);
	spr->m_pTexture = (RwTexture*)texture;
	CRGBA col;
	col.r = (uint8_t)(dwColor & 0xFF); col.g = (uint8_t)((dwColor >> 8) & 0xFF);
	col.b = (uint8_t)((dwColor >> 16) & 0xFF); col.a = (uint8_t)((dwColor >> 24) & 0xFF);
	spr->SetVertices(*rect, col, col, col, col, uv[0], uv[1], uv[2], uv[3], uv[4], uv[5], uv[6], uv[7]);
	spr->SetRenderState();
	RwIm2DRenderPrimitive(rwPRIMTYPETRIFAN, CSprite2d::maVertices, 4);
	RwRenderStateSet(rwRENDERSTATETEXTURERASTER, RWRSTATE(NULL));
	spr->m_pTexture = nullptr; // jangan sampai destruktor / pemilik lain terpengaruh
#else
	((void(*)(uintptr_t, CRect*, uint32_t*, float, float, float, float, float, float, float, float))
		(g_libGTASA + 0x6EDC5C))(texture, rect, &dwColor, uv[0], uv[1], uv[2], uv[3], uv[4], uv[5], uv[6], uv[7]);
#endif
}
""", 'DrawTextureUV 32-bit')
if '#include "sprite2d.h"' not in s:
    s = (s[:3] + '#include "sprite2d.h"\n' + s[3:]) if s.startswith('\xef\xbb\xbf') else ('#include "sprite2d.h"\n' + s)
wr(p, s)
print('OK  DrawTextureUV 32-bit tidak lagi lewat alamat hard-code (crash textdraw sprite Redmi 6A)')

# ===== BAGIAN 17: stiker / MaterialText (SetObjectMaterialText) tidak muncul =====
# Bug asli: `auto info = Encoding::cp2utf(text).c_str();` -> std::string sementara sudah hancur
# sebelum dipakai, jadi teks yang digambar sampah/kosong. Simpan string-nya dulu.
p = S + '/game/materialtextgenerator.cpp'
s = rd(p)
s = patch(s, r'auto info = Encoding::cp2utf\(text\)\.c_str\(\);',
"std::string infoStr = Encoding::cp2utf(text ? text : \"\");\n\t\tconst char* info = infoStr.c_str();",
'MaterialText dangling pointer')
wr(p, s)
print('OK  MaterialText: string teks stiker tidak lagi dangling pointer')

# ===== BAGIAN 18: FPS limiter ON=20fps, crash 32-bit saat pukul/tembak, spam lookup tekstur =====
# 18a. Frame limiter bawaan GTA: DoGameState menulis RsGlobal.maxFPS = (flag limiter ? 20 : 30).
#      Patch lama cuma mengubah cabang "30"; cabang "20" (limiter ON) tidak tersentuh -> FPS mentok 20.
p = S + '/game/patches.cpp'
s = rd(p)
s = patch(s, r'#if VER_x32\s*CHook::WriteMemory\(g_libGTASA \+ 0x005E49E0, \(uintptr_t\)& fps, 1\);\s*CHook::WriteMemory\(g_libGTASA \+ 0x005E492E, \(uintptr_t\)& fps, 1\);\s*#else',
"""#if VER_x32
    CHook::WriteMemory(g_libGTASA + 0x005E49E0, (uintptr_t)& fps, 1);
    CHook::WriteMemory(g_libGTASA + 0x005E49E6, (uintptr_t)& fps, 1); // cabang "frame limiter ON" (asli 20)
    CHook::WriteMemory(g_libGTASA + 0x005E492E, (uintptr_t)& fps, 1);
#else
    CHook::WriteMemory(g_libGTASA + 0x70A464, "\\xE8\\x0F\\x1E\\x32", 4); // mov w8,#20 -> orr w8,wzr,#60 (cabang limiter ON)""", 'FPS limiter ON cabang 20')
s = patch(s, r'(#if VER_x32\s*CHook::WriteMemory\(g_libGTASA \+ 0x005E49E0.*?\n#else\n    CHook::WriteMemory\(g_libGTASA \+ 0x70A464[^\n]*\n)\s*CHook::WriteMemory\(g_libGTASA \+ 0x70A38C', 
"""\\1    CHook::WriteMemory(g_libGTASA + 0x70A38C""", 'dummy-check') if False else s
wr(p, s)

# 18b. Crash Redmi 6A (SIGSEGV di CTaskSimpleUseGun::SetMoveAnim saat pukul/tembak):
#      di 32-bit offset libGTASA+0x4DD9E8 adalah INSTRUKSI (ldr r0,[r6,#0x18]), bukan konstanta float,
#      tapi hooks.cpp menimpanya dengan 0.015f -> instruksi rusak.
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'#if VER_x32\s*CHook::UnFuck\(g_libGTASA \+ 0x4DD9E8\);\s*\*\(float\*\)\(g_libGTASA \+ 0x4DD9E8\) = 0\.015f;\s*#else',
"#if VER_x32\n    // (dihapus) menimpa instruksi SetMoveAnim di libGTASA+0x4DD9E8 -> crash saat pukul/tembak di 32-bit\n#else", 'hapus tulis 0x4DD9E8')
wr(p, s)

# 18c. Lookup tekstur yang gagal diulang ribuan kali (ld_drv:blkdot dst.) dan tiap kegagalan menulis 6 baris log
#      (file + logcat + crashlytics). Ingat nama yang tidak ketemu, dan hilangkan log ributnya.
p = S + '/game/util.cpp'
s = rd(p)
s = patch(s, r'uintptr_t LoadTexture\(const char\* texname\)\s*\{\s*static char\* texdb\[\] = \{ "samp", "gta3", "gta_int", "player", "txd"\};.*?\n\}\n',
"""#include <unordered_set>
#include <string>
uintptr_t LoadTexture(const char* texname)
{
    static char* texdb[] = { "samp", "gta3", "gta_int", "player", "txd"};
    static std::unordered_set<std::string> s_missing;

    if (!texname) return 0;
    if (s_missing.find(texname) != s_missing.end()) return 0;

    for (int i = 0; i < sizeof(texdb) / sizeof(const char*); i++)
    {
        uintptr_t texture = (uintptr_t)CUtil::LoadTextureFromDB(texdb[i], texname);
        if (texture != 0) {
            return texture;
        }
    }

    s_missing.insert(texname);
    FLog("Texture: %s not found!", texname); // sekali saja per nama
    return 0;
}
""", 'LoadTexture negative cache')
wr(p, s)

p = S + '/util/CUtil.cpp'
s = rd(p)
s = patch(s, r'FLog\("Error: Texture \(%s\) not found in database \(%s\)", dbname, texture\);', '// (log dihapus: terlalu berisik)', 'CUtil err log')
s = patch(s, r'FLog\("WARNING! No tex = %s", name\);', '// (log dihapus: terlalu berisik)', 'CUtil warn log')
wr(p, s)
print('OK  limiter ON tidak lagi 20 FPS, crash pukul/tembak 32-bit, lookup tekstur gagal tidak diulang')

# ===== BAGIAN 19: PC -> Android tidak mengurangi darah (kebal) =====
# Di ComputeDamageResponse, baris pertama "damager bukan pemain lokal -> return true (lewati)" jalan SEBELUM
# cabang korban = pemain lokal. Akibatnya SendTakeDamageEvent tidak pernah terkirim saat pemain lain memukul/menembak
# pemain Android -> server tidak tahu, korban kebal. Android->PC aman karena damager = pemain lokal.
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'if \(pDamager != pGamePed && IsValidGamePed\(pGamePed\)\) /\* CCivilianPed \*/\s*return true;',
"""if (pDamager != pGamePed && IsValidGamePed(pGamePed)) /* CCivilianPed */
	{
		// jangan lewati bila pemain lain (remote) mengenai pemain lokal: harus dilaporkan sebagai TakeDamage
		bool remoteHitsLocal = (pPed == pGamePed) && pDamager &&
			(FindPlayerIDFromGtaPtr(pDamager) != INVALID_PLAYER_ID);
		if (!remoteHitsLocal) return true;
	}""", 'damage: remote -> local')
wr(p, s)
print('OK  damage PC->Android: TakeDamage sekarang terkirim saat pemain lain mengenai pemain lokal')

# ===== BAGIAN 20: crash SIGBUS 32-bit (ReadVector ke field struct packed), loop reload, penanda versi =====
VERSI = 'v4.1'

# 20a. SIGBUS Redmi 6A: ReadVector(float&,float&,float&) dipanggil dengan referensi ke field struct #pragma pack(1)
#      (vecMoveSpeed). Alamat field bisa tidak sejajar 4-byte, dan instruksi vstr di ARM32 mati (SIGBUS) bila begitu.
#      Baca ke float lokal dulu, baru salin dengan memcpy.
p = S + '/net/netgame.cpp'
s = rd(p)
s = patch(s, r'bsData\.ReadVector\(ofSync\.vecMoveSpeed\.x, ofSync\.vecMoveSpeed\.y, ofSync\.vecMoveSpeed\.z\);',
"""{ float acMx = 0.0f, acMy = 0.0f, acMz = 0.0f;
	bsData.ReadVector(acMx, acMy, acMz);
	memcpy(&ofSync.vecMoveSpeed.x, &acMx, sizeof(float));
	memcpy(&ofSync.vecMoveSpeed.y, &acMy, sizeof(float));
	memcpy(&ofSync.vecMoveSpeed.z, &acMz, sizeof(float)); }""", 'ReadVector onfoot aman')
s = patch(s, r'bsData\.ReadVector\(icSync\.vecMoveSpeed\.x, icSync\.vecMoveSpeed\.y, icSync\.vecMoveSpeed\.z\);',
"""{ float acMx = 0.0f, acMy = 0.0f, acMz = 0.0f;
	bsData.ReadVector(acMx, acMy, acMz);
	memcpy(&icSync.vecMoveSpeed.x, &acMx, sizeof(float));
	memcpy(&icSync.vecMoveSpeed.y, &acMy, sizeof(float));
	memcpy(&icSync.vecMoveSpeed.z, &acMz, sizeof(float)); }""", 'ReadVector incar aman')
wr(p, s)

# 20b. Loop reload di Android untuk pemain PC. Nilai byteWeaponState dari jaringan SA-MP:
#      0=tanpa peluru 1=peluru terakhir 2=masih ada peluru 3=reload. Kode membandingkan dengan enum internal GTA
#      (RELOADING=2), jadi status normal "masih ada peluru" (2) dianggap reload terus.
p = S + '/net/remoteplayer.cpp'
s = rd(p)
s = patch(s, r'if \(paimSync->byteWeaponState == WEAPONSTATE_RELOADING\)\s*\{[^}]*\}\s*else\s*if \(paimSync->byteWeaponState != WEAPONSTATE_FIRING\)\s*pwstWeapon->dwAmmoInClip = \(uint32_t\)paimSync->byteWeaponState;\s*else\s*if \(pwstWeapon->dwAmmoInClip < 2\)\s*pwstWeapon->dwAmmoInClip = 2;',
"""if (pwstWeapon)
	{
		switch (paimSync->byteWeaponState)
		{
			case 3:  if (pwstWeapon->dwState != 2) pwstWeapon->dwState = (eWeaponState)2; break; // reload (enum GTA: RELOADING = 2)
			case 2:  if (pwstWeapon->dwAmmoInClip < 30) pwstWeapon->dwAmmoInClip = 30; break;     // jangan habis di tengah tembakan
			default: pwstWeapon->dwAmmoInClip = (uint32_t)paimSync->byteWeaponState; break;
		}
	}""", 'remote weapon state mapping')
wr(p, s)

# 20c. Penanda versi di log supaya jelas build mana yang berjalan
p = S + '/game/patches.cpp'
s = rd(p)
s = patch(s, r'FLog\("New fps limit = %d", fps\);',
'FLog("New fps limit = %d", fps);\n    FLog("ACRO build %s: limiter ON/OFF = 60, SIGBUS ReadVector, reload fix, damage TAKE", "' + VERSI + '");', 'penanda versi')
wr(p, s)
print('OK  v3.3: SIGBUS ReadVector 32-bit, loop reload pemain PC, penanda versi di log')

# ============================================================ BAGIAN 21 (v3.4)
# 21a. Aim sync keluar: enum internal Android (RELOADING=2) != nilai kabel SA-MP (reload=3, masih ada peluru=2).
#      Dulu: reload dikirim 2, peluru banyak dikirim 1 -> PC melihat karakter Android terus "ngisi peluru".
p = S + '/net/localplayer.cpp'
s = rd(p)
s = patch(s, r'if \(pwstWeapon->dwState == 2\)\s*aimSync\.byteWeaponState = WEAPONSTATE_RELOADING;\s*else\s*aimSync\.byteWeaponState = \(pwstWeapon->dwAmmoInClip > 1\) \? WEAPONSTATE_FIRING : pwstWeapon->dwAmmoInClip;',
"""if (pwstWeapon->dwState == 2)
		aimSync.byteWeaponState = 3; // kabel SA-MP: 3 = reload
	else if (pwstWeapon->dwAmmoInClip > 1)
		aimSync.byteWeaponState = 2; // kabel: 2 = masih ada peluru
	else if (pwstWeapon->dwAmmoInClip == 1)
		aimSync.byteWeaponState = 1; // kabel: 1 = peluru terakhir
	else
		aimSync.byteWeaponState = (pwstWeapon->dwAmmo > 0) ? 2 : 0; // klip 0 tapi masih punya amunisi: jangan dianggap habis""", 'aim sync keluar mapping')
wr(p, s)

# 21b. Tombol mati setelah checkpoint/GPS: flag EnableGameInput(false) bisa tersangkut (keyboard/tablist
#      ditutup lewat jalur lain), baru pulih saat kirim chat (Keyboard::hide -> EnableGameInput(true)).
#      Sekarang dihitung ulang tiap sentuhan dari keadaan UI yang benar-benar tampil.
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'\tif \(pGame->IsGameInputEnabled\(\)\)\n\t\tAND_TouchEvent\(type, num, posX, posY\);',
"""\tif (!pGame->IsGameInputEnabled() && pUI &&
		!pUI->keyboard()->visible() && !pUI->dialog()->visible() && !pUI->playertablist()->visible())
	{
		FLog("Input game tersangkut nonaktif tanpa UI tampil -> dipulihkan");
		pGame->EnableGameInput(true);
	}
	if (pGame->IsGameInputEnabled())
		AND_TouchEvent(type, num, posX, posY);""", 'input game self-heal')
wr(p, s)
print('OK  v3.4: aim sync keluar (reload), input game tersangkut')

# ============================================================ BAGIAN 22 (v3.5)
# 22a. HP kendaraan: nilai di luar 0..1000 (atau NaN) tidak boleh dikirim ke server / diterapkan dari jaringan.
#      Dicatat di log supaya terlihat dari mana angka aneh (mis. 22470) berasal.
p = S + '/net/localplayer.cpp'
s = rd(p)
s = patch(s, r'icSync\.fCarHealth = pVehicle->GetHealth\(\);',
"""{ float acH = pVehicle->GetHealth();
	if (!(acH >= 0.0f && acH <= 5000.0f)) {
		static uint32_t s_acHLog = 0;
		if (GetTickCount() - s_acHLog > 2000) { s_acHLog = GetTickCount(); FLog("HP kendaraan lokal di luar batas: %.1f -> dikoreksi (model=%d)", acH, pVehicle->m_pVehicle ? (int)pVehicle->m_pVehicle->GetModelId() : -1); }
		acH = (acH != acH || acH < 0.0f) ? 0.0f : 1000.0f;
	}
	icSync.fCarHealth = acH; }""", 'hp kendaraan keluar (incar)')
s = patch(s, r'unSync\.fCarHealth = pVehicle->GetHealth\(\);',
'{ float acH = pVehicle->GetHealth(); if (!(acH >= 0.0f && acH <= 5000.0f)) acH = (acH != acH || acH < 0.0f) ? 0.0f : 1000.0f; unSync.fCarHealth = acH; }', 'hp kendaraan keluar (unoccupied)')
wr(p, s)

p = S + '/net/remoteplayer.cpp'
s = rd(p)
s = patch(s, r'm_pCurrentVehicle->SetHealth\(m_icSync\.fCarHealth\);',
'{ float acH = m_icSync.fCarHealth; if (!(acH >= 0.0f && acH <= 5000.0f)) { FLog("HP kendaraan pemain %d di luar batas: %.1f", (int)m_PlayerID, acH); acH = (acH != acH || acH < 0.0f) ? 0.0f : 1000.0f; } m_pCurrentVehicle->SetHealth(acH); }', 'hp kendaraan masuk (driver)')
s = patch(s, r'm_pCurrentVehicle->SetHealth\(picSync->fCarHealth\);',
'{ float acH = picSync->fCarHealth; if (!(acH >= 0.0f && acH <= 5000.0f)) acH = (acH != acH || acH < 0.0f) ? 0.0f : 1000.0f; m_pCurrentVehicle->SetHealth(acH); }', 'hp kendaraan masuk (penumpang)')
# 22b. Diagnosa miring kendaraan: catat arah setir PC vs kemiringan matriks yang diterapkan (1x/detik)
s = patch(s, r'm_icSync\.quat\.GetMatrix\(&matVehicle\);\n',
"""m_icSync.quat.GetMatrix(&matVehicle);
			{ static uint32_t s_acRollLog = 0; if (GetTickCount() - s_acRollLog > 1000 && m_icSync.lrAnalog) { s_acRollLog = GetTickCount();
			  FLog("ROLL pemain=%d model=%d setir=%d right.z=%.3f up.z=%.3f at.z=%.3f", (int)m_PlayerID, m_pCurrentVehicle->m_pVehicle ? (int)m_pCurrentVehicle->m_pVehicle->GetModelId() : -1, (int)(int16_t)m_icSync.lrAnalog, matVehicle.right.z, matVehicle.up.z, matVehicle.at.z); } }
""", 'diagnosa roll')
wr(p, s)
print('OK  v3.5: clamp HP kendaraan + log diagnosa roll')

# ============================================================ BAGIAN 23 (v3.6)
# Font simbol (Webdings / Wingdings / Wingdings 2,3 / Symbol) untuk material text (stiker).
# Font dibaca dari folder HP: <files>/fonts/ dan <files>/SAMP/fonts/ (tidak perlu masuk APK).
# 23a. stb_truetype: terima cmap Microsoft "Symbol" (encoding 0); kode huruf dipetakan ke U+F0xx.
p = S + '/vendor/imgui/imstb_truetype.h'
s = rd(p)
s = patch(s, r'(case STBTT_MS_EID_UNICODE_BMP:\s*case STBTT_MS_EID_UNICODE_FULL:)(\s*// MS/Unicode)',
          '\\1\n               case 0: /* MS Symbol (Webdings/Wingdings) */\\2', 'stb cmap symbol') if False else s
s = s.replace('               case STBTT_MS_EID_UNICODE_BMP:\n               case STBTT_MS_EID_UNICODE_FULL:\n                  // MS/Unicode',
              '               case 0: /* MS Symbol: Webdings/Wingdings */\n               case STBTT_MS_EID_UNICODE_BMP:\n               case STBTT_MS_EID_UNICODE_FULL:\n                  // MS/Unicode', 1)
if 'MS Symbol: Webdings' not in s:
    s = s.replace('               case STBTT_MS_EID_UNICODE_BMP:\r\n               case STBTT_MS_EID_UNICODE_FULL:\r\n                  // MS/Unicode',
                  '               case 0: /* MS Symbol: Webdings/Wingdings */\r\n               case STBTT_MS_EID_UNICODE_BMP:\r\n               case STBTT_MS_EID_UNICODE_FULL:\r\n                  // MS/Unicode', 1)
assert 'MS Symbol: Webdings' in s, 'stb cmap symbol tidak ketemu'
wr(p, s)

# 23b. imguiwrapper: muat font simbol dari folder HP ke atlas
p = S + '/gui/imguiwrapper.cpp'
s = rd(p)
SYM = r'''
#include <dirent.h>
#include <unordered_map>
#include <algorithm>
// ---- ACRO: font simbol untuk material text ----
std::unordered_map<std::string, ImFont*> g_acroSymFonts;
static std::string AcroFontKey(const char* n)
{
	std::string k;
	for (; n && *n; ++n) { char c = (char)tolower((unsigned char)*n); if (isalnum((unsigned char)c)) k += c; }
	size_t pos;
	while ((pos = k.find("wingdings")) != std::string::npos) k.replace(pos, 9, "wingding");
	if (k.size() > 3 && k.compare(k.size() - 3, 3, "ttf") == 0) k.erase(k.size() - 3);
	return k;
}
ImFont* AcroFindSymbolFont(const char* name)
{
	if (!name || !*name) return nullptr;
	auto it = g_acroSymFonts.find(AcroFontKey(name));
	return it == g_acroSymFonts.end() ? nullptr : it->second;
}
static void AcroLoadSymbolFonts(ImGuiIO& io)
{
	static const ImWchar symRanges[] = { 0x0020, 0x00FF, 0xF020, 0xF0FF, 0 };
	const char* subdirs[] = { "fonts/", "SAMP/fonts/" };
	for (const char* sub : subdirs)
	{
		std::string dir = std::string(g_pszStorage) + sub;
		DIR* d = opendir(dir.c_str());
		if (!d) { FLog("Font simbol: folder tidak ada: %s", dir.c_str()); continue; }
		while (struct dirent* e = readdir(d))
		{
			std::string fn = e->d_name;
			std::string low = fn; std::transform(low.begin(), low.end(), low.begin(), ::tolower);
			if (low.size() < 5 || low.compare(low.size() - 4, 4, ".ttf") != 0) continue;
			if (low.find("webding") == std::string::npos && low.find("wingding") == std::string::npos && low.find("symbol") == std::string::npos) continue;
			std::string key = AcroFontKey(fn.c_str());
			if (g_acroSymFonts.count(key)) continue;
			ImFontConfig cfg; cfg.OversampleH = 1; cfg.OversampleV = 1;
			ImFont* f = io.Fonts->AddFontFromFileTTF((dir + fn).c_str(), UISettings::fontSize(), &cfg, symRanges);
			FLog("Font simbol: %s -> kunci '%s' %s", (dir + fn).c_str(), key.c_str(), f ? "OK" : "GAGAL");
			if (f) g_acroSymFonts[key] = f;
		}
		closedir(d);
	}
}
'''
s = patch(s, r'(bool ImGuiWrapper::initialize\(\))', SYM + '\n\\1', 'sym fonts helper') if False else s
idx = s.index('bool ImGuiWrapper::initialize()')
s = s[:idx] + SYM + '\n' + s[idx:]
s = patch(s, r'(\tcreateFontTexture\(\);\n)', '\tAcroLoadSymbolFonts(io);\n\\1', 'sym fonts load', count=1) if False else s
assert s.count('\tcreateFontTexture();\n') >= 1
k = s.index('\tcreateFontTexture();\n', idx)
s = s[:k] + '\tAcroLoadSymbolFonts(io);\n' + s[k:]
wr(p, s)

# 23c. renderer: bisa tukar font sementara
p = S + '/gui/imguirenderer.h'
s = rd(p)
assert '\nprivate:\n\t// low-level' in s
s = s.replace('\nprivate:\n\t// low-level', '\n\tImFont* font() const { return m_font; }\n\tvoid setFont(ImFont* f) { if (f) m_font = f; }\n\nprivate:\n\t// low-level', 1)
wr(p, s)

# 23d. CObject: simpan nama font per material
p = S + '/game/object.h'
s = rd(p)
assert '\tchar* m_szMaterialText[16];' in s
s = s.replace('\tchar* m_szMaterialText[16];', '\tchar* m_szMaterialText[16];\n\tchar m_szAcroFont[16][48];', 1)
wr(p, s)
p = S + '/game/object.cpp'
s = rd(p)
s = patch(s, r'(\tstrcpy\(m_szMaterialText\[index\], text\);)',
          '\\1\n\tstrncpy(m_szAcroFont[index], fontname ? fontname : "", 47); m_szAcroFont[index][47] = 0;', 'object simpan font') if False else s
k = s.index('\tstrcpy(m_szMaterialText[index], text);')
s = s[:k] + '\tstrcpy(m_szMaterialText[index], text);\n\tstrncpy(m_szAcroFont[index], fontname ? fontname : "", 47); m_szAcroFont[index][47] = 0;' + s[k + len('\tstrcpy(m_szMaterialText[index], text);'):]
k = s.index('\t\t\tm_iMaterialFontSize[i]*=0.75f;')
s = s[:k] + '\t\t\textern const char* g_acroCurMatFont; g_acroCurMatFont = m_szAcroFont[i];\n' + s[k:]
wr(p, s)

# 23e. Render: pakai font simbol + ubah ASCII -> U+F0xx
p = S + '/game/materialtextgenerator.cpp'
s = rd(p)
s = s.replace('extern UI* pUI;', 'extern UI* pUI;\nconst char* g_acroCurMatFont = "";\nextern ImFont* AcroFindSymbolFont(const char* name);', 1)
k = s.index('\t\tconst char* info = infoStr.c_str();')
s = s[:k] + '''		ImFont* acroSym = AcroFindSymbolFont(g_acroCurMatFont);
		static std::string s_acroLastFont;
		if (s_acroLastFont != g_acroCurMatFont) { s_acroLastFont = g_acroCurMatFont; FLog("MaterialText font='%s' simbol=%d", g_acroCurMatFont, acroSym ? 1 : 0); }
		if (acroSym && text)
		{
			std::string u;
			size_t n = strlen(text);
			for (size_t i = 0; i < n; ++i)
			{
				unsigned char c = (unsigned char)text[i];
				if (c == '{' && i + 7 < n && text[i + 7] == '}') { u.append(text + i, 8); i += 7; continue; }
				if (c < 0x20) { u += (char)c; continue; }
				unsigned cp = 0xF000 + c;
				u += (char)(0xE0 | (cp >> 12)); u += (char)(0x80 | ((cp >> 6) & 0x3F)); u += (char)(0x80 | (cp & 0x3F));
			}
			infoStr = u;
		}
		ImFont* acroOldFont = pUI->renderer()->font();
		if (acroSym) pUI->renderer()->setFont(acroSym);
		const char* info = infoStr.c_str();''' + s[k + len('\t\tconst char* info = infoStr.c_str();'):]
k = s.index('\t\tpUI->renderer()->drawText(text_pos, font_color, info, false, font_size);')
ln = '\t\tpUI->renderer()->drawText(text_pos, font_color, info, false, font_size);'
s = s[:k] + ln + '\n\t\tpUI->renderer()->setFont(acroOldFont);' + s[k + len(ln):]
wr(p, s)
print('OK  v3.6: font simbol (Webdings/Wingdings) dibaca dari folder HP')

# ============================================================ BAGIAN 24 (v3.7)
# Font simbol TIDAK boleh ikut atlas utama: atlas membesar -> UV teks chat/UI rusak (teks acak-acakan).
# Dibuat atlas terpisah + tekstur sendiri; hanya dipakai saat menggambar material text bertema simbol.
p = S + '/gui/imguiwrapper.cpp'
s = rd(p)
assert 'io.Fonts->AddFontFromFileTTF((dir + fn).c_str()' in s
s = s.replace('io.Fonts->AddFontFromFileTTF((dir + fn).c_str()', 'AcroSymAtlas()->AddFontFromFileTTF((dir + fn).c_str()', 1)
s = s.replace('static void AcroLoadSymbolFonts(ImGuiIO& io)\n{',
'''static ImFontAtlas* AcroSymAtlas() { static ImFontAtlas* a = new ImFontAtlas(); return a; }
static void AcroBuildSymAtlas()
{
	ImFontAtlas* a = AcroSymAtlas();
	if (g_acroSymFonts.empty()) return;
	unsigned char* pxs; int width, height, bpp;
	a->GetTexDataAsRGBA32(&pxs, &width, &height, &bpp);
	RwImage* img = RwImageCreate(width, height, bpp * 8);
	if (!img) return;
	RwImageAllocatePixels(img);
	RwUInt8* px = img->cpPixels;
	for (int y = 0; y < img->height; y++) { memcpy((void*)px, pxs + img->stride * y, img->stride); px += img->stride; }
	RwInt32 w, h, d, flags;
	RwImageFindRasterFormat(img, rwRASTERTYPETEXTURE, &w, &h, &d, &flags);
	RwRaster* r = RwRasterCreate(w, h, d, flags);
	if (r) { r = RwRasterSetFromImage(r, img); a->TexID = (ImTextureID)r; FLog("Atlas font simbol: %dx%d", width, height); }
	RwImageDestroy(img);
}
static void AcroLoadSymbolFonts(ImGuiIO& io)
{''', 1)
k = s.index('\t\tclosedir(d);\n\t}\n}', s.index('static void AcroLoadSymbolFonts'))
s = s[:k] + '\t\tclosedir(d);\n\t}\n\tAcroBuildSymAtlas();\n}' + s[k + len('\t\tclosedir(d);\n\t}\n}'):]
wr(p, s)

p = S + '/game/materialtextgenerator.cpp'
s = rd(p)
a = '\t\tif (acroSym) pUI->renderer()->setFont(acroSym);'
assert a in s
s = s.replace(a, a + '\n\t\tif (acroSym) ImGui::GetBackgroundDrawList()->PushTextureID(acroSym->ContainerAtlas->TexID);', 1)
b = '\t\tpUI->renderer()->setFont(acroOldFont);'
assert b in s
s = s.replace(b, '\t\tif (acroSym) ImGui::GetBackgroundDrawList()->PopTextureID();\n' + b, 1)
wr(p, s)
print('OK  v3.7: font simbol pakai atlas terpisah (teks chat tidak rusak lagi)')

# ============================================================ BAGIAN 25 (v3.8)
# 25a. Memori streaming model cuma 50 MB (lihat log "STREAM: terpakai .. / tersedia 50 MB").
#      Map berat (GTA Central) membuat game membuang model terus -> bangunan/map hilang & FPS naik-turun.
#      Dinaikkan sesuai RAM HP: RAM/10, dibatasi 96..384 MB (9T ~ 384 MB, 6A ~ 190 MB).
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'void Render2dStuff\(\)\n\{\n',
"""void Render2dStuff()
{
    {
        static size_t s_acroStreamTarget = 0;
        if (!s_acroStreamTarget)
        {
            size_t total = (size_t)sysconf(_SC_PHYS_PAGES) * (size_t)sysconf(_SC_PAGESIZE);
            s_acroStreamTarget = total / 10;
            if (s_acroStreamTarget < (96u << 20)) s_acroStreamTarget = (96u << 20);
            if (s_acroStreamTarget > (384u << 20)) s_acroStreamTarget = (384u << 20);
            FLog("STREAM: RAM %zu MB -> batas memori streaming %zu MB", total >> 20, s_acroStreamTarget >> 20);
        }
        if (CStreaming::ms_memoryAvailable < s_acroStreamTarget) CStreaming::ms_memoryAvailable = s_acroStreamTarget;
    }
""", 'streaming memori naik')
if '#include <unistd.h>' not in s:
    s = s.replace('#include "../main.h"', '#include <unistd.h>\n#include "../main.h"', 1)
wr(p, s)

# 25b. Buang log debug per-langkah di MaterialTextGenerator::Generate (9 baris log per stiker = lambat)
import re as _re
p = S + '/game/materialtextgenerator.cpp'
s = rd(p)
s, n = _re.subn(r'[ \t]*FLog\("MaterialTextGenerator::Generate\d*"\);\r?\n', '', s)
assert n >= 5, 'log generate tidak ketemu'
wr(p, s)
print('OK  v3.8: memori streaming naik (map hilang), log stiker dibuang')

# ============================================================ BAGIAN 26 (v3.9)
# 26a. SUARA VOICE: audio stream (musik) menginisialisasi BASS lebih dulu -> BASS_Init milik voice gagal
#      (error 14 = sudah aktif) -> modul voice menganggap gagal dan tidak pernah memutar suara.
#      Sekarang: stream memakai flag 3D yang sama, dan voice menerima error 14 sebagai "sudah siap".
p = S + '/voice_new/Playback.cpp'
s = rd(p)
s = patch(s, r'if\(BASS_Init\(-1, SV::kFrequency, BASS_DEVICE_MONO \| BASS_DEVICE_3D, nullptr, nullptr\) == 0\)\n    \{',
"""if(BASS_Init(-1, SV::kFrequency, BASS_DEVICE_MONO | BASS_DEVICE_3D, nullptr, nullptr) == 0 && BASS_ErrorGetCode() != BASS_ERROR_ALREADY)
    {
        FLog("[sv:err] BASS_Init voice gagal: %d", BASS_ErrorGetCode());""", 'voice bass init')
s = patch(s, r'LogVoice\("\[sv:dbg:playback:bassinithook\] : module loaded"\);',
          'LogVoice("[sv:dbg:playback:bassinithook] : module loaded"); FLog("[sv] voice playback siap");', 'voice siap log')
wr(p, s)

# 26b. Diagnosa memori HP di baris STREAM (RAM bebas dari /proc/meminfo) untuk melacak tekstur putih/abu-abu
p = S + '/game/hooks.cpp'
s = rd(p)
k = s.index('FLog("STREAM: terpakai')
e = s.index('\n', k)
s = s[:e+1] + """            { FILE* acroMf = fopen("/proc/meminfo", "r"); if (acroMf) { char ln[128]; long acroAvail = -1; while (fgets(ln, sizeof ln, acroMf)) if (sscanf(ln, "MemAvailable: %ld kB", &acroAvail) == 1) break; fclose(acroMf); FLog("MEM: RAM bebas %ld MB", acroAvail / 1024); } }
""" + s[e+1:]
wr(p, s)
print('OK  v3.9: voice BASS_Init, diagnosa RAM')

# ============================================================ BAGIAN 27 (v4.0)
# Jarak pandang (far clip) dibatasi: map besar + LOD jauh = berat di GPU Adreno 610 dan tekstur LOD putih.
# Bisa diatur lewat <files>/SAMP/settings.ini  ->  FarClip=450   (0 = tidak dibatasi). Default 450 m.
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'void InstallSpecialHooks\(\)\n\{\n    InjectHooks\(\);\n',
"""static RwCamera* (*acroRwCameraSetFarClipPlane)(RwCamera*, RwReal) = nullptr;
static float g_acroFarLimit = 450.0f;
static RwCamera* acroRwCameraSetFarClipPlane_hook(RwCamera* cam, RwReal farClip)
{
    static float s_maxSeen = 0;
    if (farClip > s_maxSeen) { s_maxSeen = farClip; FLog("FARCLIP: game minta %.0f m (batas client %.0f m)", farClip, g_acroFarLimit); }
    if (g_acroFarLimit > 0.0f && farClip > g_acroFarLimit) farClip = g_acroFarLimit;
    return acroRwCameraSetFarClipPlane(cam, farClip);
}

void InstallSpecialHooks()
{
    InjectHooks();

    {
        char acroPath[256];
        snprintf(acroPath, sizeof(acroPath), "%sSAMP/settings.ini", g_pszStorage);
        if (FILE* acroF = fopen(acroPath, "r"))
        {
            char ln[160];
            while (fgets(ln, sizeof ln, acroF)) { float v; if (sscanf(ln, " FarClip = %f", &v) == 1) g_acroFarLimit = v; }
            fclose(acroF);
        }
        FLog("FARCLIP: batas jarak pandang = %.0f m (0 = bebas)", g_acroFarLimit);
        CHook::InlineHook(g_libGTASA + (VER_x32 ? 0x001D5ACC + 1 : 0x26D034), &acroRwCameraSetFarClipPlane_hook, &acroRwCameraSetFarClipPlane);
    }
""", 'far clip hook')
wr(p, s)
print('OK  v4.0: batas jarak pandang (FarClip) lewat settings.ini')

# ============================================================ BAGIAN 28 (v4.1)
# 28a. Profiler render: ukur waktu fungsi-fungsi berat game per 5 detik (baris "RENDER 5dtk: ..." di log).
#      Supaya terlihat apa yang makan ~40 ms/frame (HUD+UI+NET hanya ~5 ms).
p = S + '/game/hooks.cpp'
s = rd(p)
s = patch(s, r'void Render2dStuff\(\)\n\{\n',
'''#include <time.h>
#include <dlfcn.h>
struct AcroProfSlot { const char* name; double ms; int calls; void* orig; };
static AcroProfSlot g_acroProf[7] = { {"NonRoad"}, {"RoadsBld"}, {"RenderList"}, {"PreRender"}, {"GameProc"}, {"Streaming"}, {"WorldProc"} };
static inline double acroNow() { struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts); return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6; }
#define ACRO_PROF_FN(I) static void acroProfFn##I() { double t = acroNow(); ((void(*)())g_acroProf[I].orig)(); g_acroProf[I].ms += acroNow() - t; g_acroProf[I].calls++; }
ACRO_PROF_FN(1) ACRO_PROF_FN(2) ACRO_PROF_FN(3) ACRO_PROF_FN(4) ACRO_PROF_FN(5) ACRO_PROF_FN(6)
void Render2dStuff()
{
''', 'profiler struct')
s = patch(s, r'\n\tCRenderer_RenderEverythingBarRoads\(\);\n',
"""
	{ double acroT = acroNow(); CRenderer_RenderEverythingBarRoads(); g_acroProf[0].ms += acroNow() - acroT; g_acroProf[0].calls++; }
""", 'profiler nonroad')
# pasang hook tambahan (dlsym, dilewati kalau simbol tidak ada)
s = patch(s, r'        FLog\("FARCLIP: batas jarak pandang',
"""        {
            static void (*fns[7])() = { nullptr, acroProfFn1, acroProfFn2, acroProfFn3, acroProfFn4, acroProfFn5, acroProfFn6 };
            static const char* syms[7] = { nullptr, "_ZN9CRenderer21RenderRoadsAndBuildingsEv", "_ZN9CRenderer13ConstructRenderListEv",
                "_ZN9CRenderer9PreRenderEv", "_ZN5CGame7ProcessEv", "_ZN10CStreaming6UpdateEv", "_ZN6CWorld7ProcessEv" };
            for (int i = 1; i < 7; i++)
            {
                void* a = dlsym(CHook::lib, syms[i]);
                if (a) CHook::InlineHook((uintptr_t)a, fns[i], (void**)&g_acroProf[i].orig);
                FLog("PROFIL render: %s %s", syms[i], a ? "dipasang" : "TIDAK ADA");
            }
        }
        FLog("FARCLIP: batas jarak pandang""", 'profiler pasang')
# cetak tiap 5 detik di samping baris MEM
k = s.index('FLog("MEM: RAM bebas')
e = s.index('\n', k)
s = s[:e+1] + """            { char rb[256]; int n = snprintf(rb, sizeof rb, "RENDER 5dtk:");
              for (int i = 0; i < 7; i++) { if (g_acroProf[i].calls) n += snprintf(rb + n, sizeof rb - n, " %s=%.0fms/%dx", g_acroProf[i].name, g_acroProf[i].ms, g_acroProf[i].calls); g_acroProf[i].ms = 0; g_acroProf[i].calls = 0; }
              FLog("%s", rb); }
""" + s[e+1:]
wr(p, s)

# 28b. Voice: catat kiriman keepalive UDP & tidak adanya pluginInit (server tidak membalas)
p = S + '/voice_new/Network.cpp'
s = rd(p)
s = patch(s, r'send\(Network::socketHandle, reinterpret_cast<const char \*>\(&keepAlivePacket\),\n\s*sizeof\(keepAlivePacket\), NULL\);',
"""{
                static int s_acroKa = 0;
                const auto kaRes = send(Network::socketHandle, reinterpret_cast<const char *>(&keepAlivePacket), sizeof(keepAlivePacket), NULL);
                if (s_acroKa < 3 || (curStatus != ConnectionStatus::Connected && (s_acroKa % 20) == 0))
                    FLog("[sv] keepalive UDP #%d hasil=%d errno=%d status=%d (belum Connected = server belum membalas pluginInit)", s_acroKa, (int)kaRes, kaRes < 0 ? errno : 0, (int)curStatus);
                s_acroKa++;
            }""", 'voice keepalive log')
if '#include <errno.h>' not in s:
    s = '#include <errno.h>\n' + s
wr(p, s)
print('OK  v4.1: profiler render, log voice keepalive, StaticShadows default ON')
