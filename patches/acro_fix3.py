#!/usr/bin/env python3
# Patch tahap 6 (jalankan SETELAH patches/acro_fix2.py).
# (1) analog/tombol bawaan GTA disembunyikan + dikunci saat layar pilih karakter / textdraw pilih aktif
# (2) tombol Spawn/textdraw lebih mudah ditekan (toleransi area sentuh) + log diagnosa
# (3) tombol Tempel jadi ikon clipboard, kolom input lebih transparan
# (4) keyboard tertutup bila disentuh di luar area keyboard (tanpa mengirim)
# (5) ikon AFK lebih lambat muncul (animasi repair mekanik, dll)
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
