#!/usr/bin/env python3
# Patch tahap 5 (jalankan SETELAH patches/acro_ui.py).
# Perbaikan: (1) audio stream, (2) kolom input + tombol << >> / bisa diklik, (3) hapus tombol RUS.
import re

S = 'app/src/main/cpp/samp'


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
