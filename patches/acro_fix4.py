#!/usr/bin/env python3
# Patch tahap 7 (jalankan SETELAH patches/acro_fix3.py).
# Semua poin di sini berdasarkan bukti dari samp_log.txt dan pembacaan kode:
#  1. Mod kendaraan (velg, NOS), paintjob, warna body tidak pernah diterapkan -> diterapkan saat kendaraan dibuat
#  2. Senjata desync: SetArmedWeapon() kosong, GiveWeapon(0) tidak melepas senjata -> tangan kosong benar-benar dipasang
#  3. Karakter Android terlihat AFK di PC: sync jalan kaki tidak dikirim ulang saat diam -> heartbeat 700 ms
#  4. Layar pilih karakter: textdraw selectable transparan selebar layar menelan sentuhan -> pilih yang LUASNYA terkecil
#  5. Kontrol game dikunci/disembunyikan juga saat server membekukan pemain (TogglePlayerControllable false)
#  6. Penumpang tidak lagi melihat tombol setir/gas/rem/klakson; tombol tinju disembunyikan di dalam kendaraan
#  7. Tombol G di panel diganti ikon penumpang
#  8. Diagnosa: log id RPC yang pertama kali masuk (untuk melacak audio stream dan mod runtime)
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


def patch_keep(s, pat, fn, name, count=1, flags=re.S):
    """seperti patch(), tapi fn(match) -> teks pengganti (bisa memakai grup)"""
    n = len(re.findall(pat, s, flags))
    assert n == count, 'PATCH GAGAL [%s]: ditemukan %d, seharusnya %d' % (name, n, count)
    return re.sub(pat, fn, s, flags=flags)


# ------------------------------------------------------------ 1. Mod kendaraan saat kendaraan dibuat
p = S + '/net/vehiclepool.cpp'
s = rd(p)
MODS = '''m_pVehicles[new_veh->VehicleID]->SetHealth(new_veh->fHealth);

    // fix tahap 7: terapkan mod (velg, NOS, dll), paintjob dan warna body dari server.
    // Dulu blok ini dikomentari sehingga kendaraan selalu tampil standar di Android.
    {
        CVehicle* pModVeh = m_pVehicles[new_veh->VehicleID];
        int iModCount = 0;
        for (int i = 0; i < 14; i++)
        {
            uint8_t byteMod = new_veh->byteModSlots[i];
            if (!byteMod) continue;
            try { pModVeh->AddComponent(byteMod + 999); iModCount++; }
            catch (...) { FLog("Mod kendaraan gagal: veh=%d mod=%d", (int)new_veh->VehicleID, (int)byteMod + 999); }
        }
        if (new_veh->bytePaintJob) pModVeh->SetPaintJob(new_veh->bytePaintJob - 1);
        if (new_veh->iBodyColor1 != -1 || new_veh->iBodyColor2 != -1)
        {
            int c1 = (new_veh->iBodyColor1 != -1) ? new_veh->iBodyColor1 : new_veh->byteInteriorColor1;
            int c2 = (new_veh->iBodyColor2 != -1) ? new_veh->iBodyColor2 : new_veh->byteInreriorColor2;
            pModVeh->SetColor((uint8_t)c1, (uint8_t)c2);
        }
        if (iModCount || new_veh->bytePaintJob)
            FLog("Kendaraan %d: mod=%d paintjob=%d diterapkan", (int)new_veh->VehicleID, iModCount, (int)new_veh->bytePaintJob);
    }'''
s = patch(s, r'm_pVehicles\[new_veh->VehicleID\]->SetHealth\(new_veh->fHealth\);', MODS, 'vehicle mods')
wr(p, s)
print('OK  mod/paintjob/warna kendaraan saat dibuat')

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
