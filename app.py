import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import date, timedelta

from utils import (
    init_data,
    load_transaksi,
    add_transaksi,
    add_transfer,
    update_transaksi,
    delete_transaksi,
    load_proker,
    add_proker,
    delete_proker,
    load_anggota,
    add_anggota,
    delete_anggota,
    get_nominal_kas_mingguan,
    set_nominal_kas_mingguan,
    load_iuran,
    mark_iuran_paid,
    unmark_iuran_paid,
    format_rupiah,
    hitung_ringkasan,
    hitung_ringkasan_per_kas,
    generate_excel,
    generate_pdf,
    KATEGORI_DEFAULT,
    KATEGORI_INPUT_MANUAL,
    KAS_OPTIONS,
    PROKER_UMUM_PLACEHOLDER,
)
import theme

st.set_page_config(
    page_title="Keuangan KKN",
    page_icon="💰",
    layout="wide",
)

theme.inject()
init_data()

theme.render_sidebar_title("KEUANGAN", "KKN", badge_text="✅ SISTEM AKTIF")
menu = st.sidebar.radio(
    "Menu",
    [
        "📊 Dashboard",
        "➕ Input Transaksi",
        "🔁 Transfer Antar Kas",
        "✅ Iuran Kas Anggota",
        "📋 Riwayat & Kelola",
        "🗂️ Manajemen Proker/Kegiatan",
        "📑 Laporan & Export",
    ],
)

st.sidebar.markdown("---")
st.sidebar.caption("Aplikasi Pencatatan Keuangan Bendahara KKN • Data tersimpan otomatis di Google Sheets")

if menu == "📊 Dashboard":
    theme.render_title("DASHBOARD", "KEUANGAN")

    df = load_transaksi()
    ringkasan_kas = hitung_ringkasan_per_kas(df)

    col1, col2, col3 = st.columns(3)
    col1.metric("💼 Saldo Kas Umum", format_rupiah(ringkasan_kas["Kas Umum"]["saldo"]))
    col2.metric("🎯 Saldo Kas Proker", format_rupiah(ringkasan_kas["Kas Proker"]["saldo"]))
    col3.metric("🏦 Total Keseluruhan", format_rupiah(ringkasan_kas["Total"]["saldo"]))

    with st.expander("Lihat rincian pemasukan & pengeluaran per kas"):
        rincian = pd.DataFrame({
            "Kas": ["Kas Umum", "Kas Proker", "Total"],
            "Total Pemasukan": [format_rupiah(ringkasan_kas[k]["total_pemasukan"]) for k in ["Kas Umum", "Kas Proker", "Total"]],
            "Total Pengeluaran": [format_rupiah(ringkasan_kas[k]["total_pengeluaran"]) for k in ["Kas Umum", "Kas Proker", "Total"]],
            "Saldo": [format_rupiah(ringkasan_kas[k]["saldo"]) for k in ["Kas Umum", "Kas Proker", "Total"]],
        })
        st.dataframe(rincian, width="stretch", hide_index=True)

    theme.divider()

    if df.empty:
        st.info("Belum ada transaksi. Silakan tambahkan transaksi melalui menu **Input Transaksi**.")
    else:
        kas_filter = st.radio("Tampilkan grafik untuk:", ["Semua Kas"] + KAS_OPTIONS, horizontal=True)
        df_chart = df if kas_filter == "Semua Kas" else df[df["Kas"] == kas_filter]

        c1, c2 = st.columns(2)

        with c1:
            st.subheader("Pengeluaran per Kategori")
            df_keluar = df_chart[df_chart["Jenis"] == "Pengeluaran"]
            if not df_keluar.empty:
                rekap = df_keluar.groupby("Kategori")["Jumlah"].sum().reset_index()
                fig = px.pie(rekap, names="Kategori", values="Jumlah", hole=0.4)
                fig.update_traces(textinfo="percent+label")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("Belum ada data pengeluaran untuk filter ini.")

        with c2:
            st.subheader("Pemasukan vs Pengeluaran per Proker")
            rekap_proker = df_chart.groupby(["Proker", "Jenis"])["Jumlah"].sum().reset_index()
            if not rekap_proker.empty:
                fig2 = px.bar(
                    rekap_proker, x="Proker", y="Jumlah", color="Jenis",
                    barmode="group", text_auto=".2s",
                )
                fig2.update_layout(xaxis_title="", yaxis_title="Jumlah (Rp)")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.caption("Belum ada data untuk filter ini.")

        st.subheader("Tren Saldo Kas Harian")
        df_harian = df_chart.copy()
        df_harian["Tanggal"] = pd.to_datetime(df_harian["Tanggal"])
        df_harian["Arus"] = df_harian.apply(
            lambda r: r["Jumlah"] if r["Jenis"] == "Pemasukan" else -r["Jumlah"], axis=1
        )
        harian = df_harian.groupby(df_harian["Tanggal"].dt.date)["Arus"].sum().sort_index().cumsum().reset_index()
        harian.columns = ["Tanggal", "Saldo Kumulatif"]

        if len(harian) < 2:
            info_saldo = format_rupiah(harian["Saldo Kumulatif"].iloc[0]) if not harian.empty else "Rp 0"
            st.info(
                "Grafik tren akan muncul setelah ada transaksi di **minimal 2 tanggal berbeda**. "
                f"Saat ini baru ada transaksi di 1 tanggal, dengan saldo {info_saldo}."
            )
        else:
            fig3 = px.line(harian, x="Tanggal", y="Saldo Kumulatif", markers=True)
            fig3.update_yaxes(rangemode="tozero")
            st.plotly_chart(fig3, use_container_width=True)

elif menu == "➕ Input Transaksi":
    theme.render_title("INPUT", "TRANSAKSI")

    daftar_proker = load_proker()

    col_top1, col_top2 = st.columns(2)
    with col_top1:
        jenis = st.radio("Jenis Transaksi", ["Pemasukan", "Pengeluaran"], horizontal=True)
    with col_top2:
        kas = st.radio("Kas", KAS_OPTIONS, horizontal=True)

    with st.form("form_input", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tanggal = st.date_input("Tanggal", value=date.today())
            if kas == "Kas Proker":
                proker = st.selectbox("Proker / Kegiatan", daftar_proker)
            else:
                st.text_input("Proker / Kegiatan", value=PROKER_UMUM_PLACEHOLDER, disabled=True)
                proker = PROKER_UMUM_PLACEHOLDER
        with col2:
            kategori = st.selectbox("Kategori", KATEGORI_INPUT_MANUAL[jenis])
            jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1000, format="%d")

        keterangan = st.text_area("Keterangan", placeholder="Contoh: Pembelian konsumsi rapat proker Posyandu")

        submitted = st.form_submit_button("💾 Simpan Transaksi", width="stretch")

        if submitted:
            if jumlah <= 0:
                st.error("Jumlah harus lebih besar dari 0.")
            else:
                add_transaksi(tanggal, jenis, kas, proker, kategori, keterangan, jumlah)
                st.success(f"Transaksi {jenis.lower()} ({kas}) sebesar {format_rupiah(jumlah)} berhasil disimpan.")

    if kas == "Kas Proker" and not daftar_proker:
        st.warning("Belum ada proker/kegiatan. Tambahkan dahulu di menu **Manajemen Proker/Kegiatan**.")

    st.caption("💡 Untuk mencatat perpindahan dana antar Kas Umum dan Kas Proker, gunakan menu **Transfer Antar Kas** agar saldo kedua kas tetap seimbang.")

elif menu == "🔁 Transfer Antar Kas":
    theme.render_title("TRANSFER", "ANTAR KAS")
    st.caption("Gunakan menu ini untuk memindahkan dana antara Kas Umum dan Kas Proker, misalnya alokasi modal awal kegiatan.")

    daftar_proker = load_proker()

    if not daftar_proker:
        st.warning("Belum ada proker/kegiatan. Tambahkan dahulu di menu **Manajemen Proker/Kegiatan** sebelum melakukan transfer.")
    else:
        with st.form("form_transfer", clear_on_submit=True):
            arah = st.radio("Arah Transfer", ["Kas Umum ke Kas Proker", "Kas Proker ke Kas Umum"])

            col1, col2 = st.columns(2)
            with col1:
                tanggal = st.date_input("Tanggal", value=date.today())
                proker = st.selectbox("Proker / Kegiatan Terkait", daftar_proker)
            with col2:
                jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1000, format="%d")

            keterangan = st.text_area("Keterangan (opsional)", placeholder="Contoh: Modal awal kegiatan Posyandu Balita")

            submitted = st.form_submit_button("🔁 Simpan Transfer", width="stretch")

            if submitted:
                if jumlah <= 0:
                    st.error("Jumlah harus lebih besar dari 0.")
                else:
                    add_transfer(tanggal, arah, proker, jumlah, keterangan)
                    st.success(f"Transfer {format_rupiah(jumlah)} ({arah}) berhasil dicatat.")

        theme.divider()
        st.subheader("Riwayat Transfer")
        df = load_transaksi()
        df_transfer = df[df["Kategori"] == "Transfer Antar Kas"].sort_values("Tanggal", ascending=False)
        if df_transfer.empty:
            st.caption("Belum ada riwayat transfer.")
        else:
            tampil = df_transfer.copy()
            tampil["Tanggal"] = tampil["Tanggal"].dt.strftime("%d-%m-%Y")
            tampil["Jumlah"] = tampil["Jumlah"].apply(format_rupiah)
            st.dataframe(
                tampil[["Tanggal", "Jenis", "Kas", "Proker", "Keterangan", "Jumlah"]],
                width="stretch", hide_index=True,
            )

elif menu == "✅ Iuran Kas Anggota":
    theme.render_title("IURAN KAS", "ANGGOTA")

    daftar_anggota = load_anggota()
    nominal = get_nominal_kas_mingguan()

    tab1, tab2, tab3, tab4 = st.tabs(
        ["✅ Tandai Pembayaran", "📊 Rekap Mingguan", "👥 Kelola Anggota", "⚙️ Pengaturan"]
    )

    with tab1:
        if nominal <= 0:
            st.warning("Nominal kas mingguan belum diatur. Silakan atur dulu di tab **⚙️ Pengaturan**.")
        if not daftar_anggota:
            st.warning("Belum ada anggota. Tambahkan dulu di tab **👥 Kelola Anggota**.")
        else:
            tgl_pilih = st.date_input("Pilih tanggal (minggu akan otomatis terdeteksi)", value=date.today())
            senin = tgl_pilih - timedelta(days=tgl_pilih.weekday())
            minggu_label = senin.isoformat()
            minggu_display = f"{senin.strftime('%d %b')} - {(senin + timedelta(days=6)).strftime('%d %b %Y')}"
            st.markdown(f"**Minggu: {minggu_display}**  •  Nominal per anggota: **{format_rupiah(nominal)}**")

            df_iuran = load_iuran()
            paid_set = set(df_iuran[df_iuran["Minggu"] == minggu_label]["Nama Anggota"])

            sudah = len(paid_set)
            belum = len(daftar_anggota) - sudah
            c1, c2, c3 = st.columns(3)
            c1.metric("Sudah Bayar", f"{sudah} orang")
            c2.metric("Belum Bayar", f"{belum} orang")
            c3.metric("Total Terkumpul", format_rupiah(sudah * nominal))

            theme.divider()
            for nama in daftar_anggota:
                sudah_bayar = nama in paid_set
                key_cb = f"iuran_{minggu_label}_{nama}"
                confirm_key = f"confirm_unmark_{minggu_label}_{nama}"

                checked = st.checkbox(nama, value=sudah_bayar, key=key_cb)

                if checked and not sudah_bayar:
                    if nominal <= 0:
                        st.error("Atur nominal kas mingguan terlebih dahulu sebelum menandai pembayaran.")
                        st.session_state[key_cb] = False
                        st.rerun()
                    else:
                        mark_iuran_paid(minggu_label, nama, tgl_pilih)
                        st.rerun()

                elif not checked and sudah_bayar:
                    st.session_state[confirm_key] = True

                if st.session_state.get(confirm_key):
                    st.warning(f"Yakin membatalkan status bayar **{nama}** untuk minggu ini? Transaksi terkait akan dihapus permanen.")
                    colA, colB = st.columns(2)
                    if colA.button("✅ Ya, batalkan", key=f"ya_{confirm_key}", width="stretch"):
                        unmark_iuran_paid(minggu_label, nama)
                        st.session_state[confirm_key] = False
                        st.rerun()
                    if colB.button("↩️ Batal, tetap tandai bayar", key=f"tidak_{confirm_key}", width="stretch"):
                        st.session_state[confirm_key] = False
                        st.session_state[key_cb] = True
                        st.rerun()

    with tab2:
        st.subheader("Rekap Status Iuran per Minggu")
        df_iuran_all = load_iuran()
        if not daftar_anggota:
            st.caption("Belum ada anggota.")
        elif df_iuran_all.empty:
            st.caption("Belum ada riwayat pembayaran iuran.")
        else:
            minggu_list = sorted(df_iuran_all["Minggu"].unique())
            kolom_label = {
                m: f"{pd.Timestamp(m).strftime('%d %b')}-{(pd.Timestamp(m)+timedelta(days=6)).strftime('%d %b')}"
                for m in minggu_list
            }
            pivot = pd.DataFrame(index=daftar_anggota)
            for m in minggu_list:
                paid_names = set(df_iuran_all[df_iuran_all["Minggu"] == m]["Nama Anggota"])
                pivot[kolom_label[m]] = ["✅" if n in paid_names else "❌" for n in daftar_anggota]
            pivot.index.name = "Nama Anggota"
            st.dataframe(pivot, width="stretch")

            total_terkumpul = len(df_iuran_all) * nominal
            st.caption(f"Total dana iuran terkumpul sepanjang waktu: **{format_rupiah(total_terkumpul)}**")

    with tab3:
        st.subheader("Daftar Anggota Saat Ini")
        if daftar_anggota:
            st.write(", ".join(daftar_anggota))
        else:
            st.info("Belum ada anggota.")

        theme.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("➕ Tambah Anggota")
            nama_baru = st.text_input("Nama Anggota", key="tambah_anggota")
            if st.button("Tambah", key="btn_tambah_anggota", width="stretch"):
                if nama_baru.strip():
                    add_anggota(nama_baru)
                    st.success(f"Anggota '{nama_baru}' ditambahkan.")
                    st.rerun()
                else:
                    st.error("Nama tidak boleh kosong.")
        with col2:
            st.subheader("🗑️ Hapus Anggota")
            if daftar_anggota:
                anggota_hapus = st.selectbox("Pilih anggota", daftar_anggota, key="hapus_anggota")
                if st.button("Hapus", key="btn_hapus_anggota", width="stretch"):
                    delete_anggota(anggota_hapus)
                    st.success(f"Anggota '{anggota_hapus}' dihapus.")
                    st.rerun()
        st.caption("Catatan: Menghapus anggota tidak akan menghapus riwayat pembayaran iuran yang sudah tercatat.")

    with tab4:
        st.subheader("Nominal Kas Mingguan")
        st.caption("Nominal ini berlaku sama untuk semua anggota setiap minggunya.")
        nominal_baru = st.number_input(
            "Nominal per anggota per minggu (Rp)", min_value=0, step=1000, value=int(nominal), format="%d"
        )
        if st.button("💾 Simpan Nominal", width="stretch"):
            set_nominal_kas_mingguan(nominal_baru)
            st.success(f"Nominal kas mingguan disimpan: {format_rupiah(nominal_baru)}")
            st.rerun()

elif menu == "📋 Riwayat & Kelola":
    theme.render_title("RIWAYAT", "TRANSAKSI")

    df = load_transaksi()

    if df.empty:
        st.info("Belum ada transaksi.")
    else:
        with st.expander("🔍 Filter Data", expanded=True):
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1:
                tgl_mulai = st.date_input("Dari tanggal", value=df["Tanggal"].min().date())
            with c2:
                tgl_akhir = st.date_input("Sampai tanggal", value=df["Tanggal"].max().date())
            with c3:
                filter_kas = st.multiselect("Kas", KAS_OPTIONS, default=KAS_OPTIONS)
            with c4:
                filter_jenis = st.multiselect("Jenis", ["Pemasukan", "Pengeluaran"], default=["Pemasukan", "Pengeluaran"])
            with c5:
                filter_proker = st.multiselect("Proker", sorted(df["Proker"].unique()), default=sorted(df["Proker"].unique()))

        mask = (
            (df["Tanggal"].dt.date >= tgl_mulai)
            & (df["Tanggal"].dt.date <= tgl_akhir)
            & (df["Kas"].isin(filter_kas))
            & (df["Jenis"].isin(filter_jenis))
            & (df["Proker"].isin(filter_proker))
        )
        df_filtered = df[mask].sort_values("Tanggal", ascending=False)

        st.markdown(f"**{len(df_filtered)} transaksi ditemukan**")

        tampil = df_filtered.copy()
        tampil["Tanggal"] = tampil["Tanggal"].dt.strftime("%d-%m-%Y")
        tampil["Jumlah"] = tampil["Jumlah"].apply(format_rupiah)
        st.dataframe(
            tampil[["ID", "Tanggal", "Jenis", "Kas", "Proker", "Kategori", "Keterangan", "Jumlah"]],
            width="stretch", hide_index=True,
        )

        theme.divider()
        st.subheader("✏️ Edit / 🗑️ Hapus Transaksi")
        st.caption("⚠️ Untuk transaksi hasil Transfer Antar Kas, edit/hapus dilakukan satu per satu (kedua sisi transfer tidak otomatis ikut berubah).")

        if not df_filtered.empty:
            opsi_id = df_filtered["ID"].tolist()
            id_pilih = st.selectbox(
                "Pilih ID transaksi",
                opsi_id,
                format_func=lambda x: f"ID {x} - {df_filtered.loc[df_filtered['ID']==x, 'Keterangan'].values[0]}",
            )
            row = df_filtered[df_filtered["ID"] == id_pilih].iloc[0]

            daftar_proker = load_proker()
            with st.form("form_edit"):
                col1, col2 = st.columns(2)
                with col1:
                    e_tanggal = st.date_input("Tanggal", value=row["Tanggal"].date())
                    e_jenis = st.radio("Jenis", ["Pemasukan", "Pengeluaran"], index=0 if row["Jenis"] == "Pemasukan" else 1, horizontal=True)
                    e_kas = st.radio("Kas", KAS_OPTIONS, index=KAS_OPTIONS.index(row["Kas"]) if row["Kas"] in KAS_OPTIONS else 0, horizontal=True)
                with col2:
                    idx_proker = daftar_proker.index(row["Proker"]) if row["Proker"] in daftar_proker else 0
                    e_proker = st.selectbox("Proker", daftar_proker, index=idx_proker)
                    kategori_list = KATEGORI_DEFAULT[e_jenis]
                    idx_kat = kategori_list.index(row["Kategori"]) if row["Kategori"] in kategori_list else 0
                    e_kategori = st.selectbox("Kategori", kategori_list, index=idx_kat)
                e_jumlah = st.number_input("Jumlah (Rp)", min_value=0, step=1000, value=int(row["Jumlah"]), format="%d")
                e_keterangan = st.text_area("Keterangan", value=row["Keterangan"])

                colA, colB = st.columns(2)
                simpan = colA.form_submit_button("💾 Simpan Perubahan", width="stretch")
                hapus = colB.form_submit_button("🗑️ Hapus Transaksi", width="stretch")

                if simpan:
                    update_transaksi(id_pilih, e_tanggal, e_jenis, e_kas, e_proker, e_kategori, e_keterangan, e_jumlah)
                    st.success("Perubahan disimpan.")
                    st.rerun()

                if hapus:
                    delete_transaksi(id_pilih)
                    st.success(f"Transaksi ID {id_pilih} dihapus.")
                    st.rerun()

elif menu == "🗂️ Manajemen Proker/Kegiatan":
    theme.render_title("MANAJEMEN", "PROKER")

    daftar_proker = load_proker()

    st.subheader("Daftar Proker/Kegiatan Saat Ini")
    if daftar_proker:
        st.write(", ".join(daftar_proker))
    else:
        st.info("Belum ada proker/kegiatan.")

    theme.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("➕ Tambah Proker Baru")
        nama_baru = st.text_input("Nama Proker/Kegiatan", key="tambah_proker")
        if st.button("Tambah", width="stretch"):
            if nama_baru.strip():
                add_proker(nama_baru)
                st.success(f"Proker '{nama_baru}' ditambahkan.")
                st.rerun()
            else:
                st.error("Nama proker tidak boleh kosong.")

    with col2:
        st.subheader("🗑️ Hapus Proker")
        if daftar_proker:
            proker_hapus = st.selectbox("Pilih proker yang akan dihapus", daftar_proker, key="hapus_proker")
            if st.button("Hapus", width="stretch"):
                delete_proker(proker_hapus)
                st.success(f"Proker '{proker_hapus}' dihapus.")
                st.rerun()

    st.caption("Catatan: Menghapus proker tidak akan menghapus transaksi yang sudah tercatat menggunakan proker tersebut.")

elif menu == "📑 Laporan & Export":
    theme.render_title("LAPORAN", "& EXPORT")

    df = load_transaksi()

    if df.empty:
        st.info("Belum ada transaksi untuk dilaporkan.")
    else:
        with st.expander("🔍 Filter Laporan", expanded=True):
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                tgl_mulai = st.date_input("Dari tanggal", value=df["Tanggal"].min().date(), key="lap_mulai")
            with c2:
                tgl_akhir = st.date_input("Sampai tanggal", value=df["Tanggal"].max().date(), key="lap_akhir")
            with c3:
                filter_kas = st.multiselect("Kas (kosongkan = semua)", KAS_OPTIONS, key="lap_kas")
            with c4:
                filter_proker = st.multiselect(
                    "Proker (kosongkan = semua)", sorted(df["Proker"].unique()), key="lap_proker"
                )

        mask = (df["Tanggal"].dt.date >= tgl_mulai) & (df["Tanggal"].dt.date <= tgl_akhir)
        if filter_kas:
            mask &= df["Kas"].isin(filter_kas)
        if filter_proker:
            mask &= df["Proker"].isin(filter_proker)
        df_laporan = df[mask].sort_values("Tanggal")

        ringkasan_kas = hitung_ringkasan_per_kas(df_laporan)
        col1, col2, col3 = st.columns(3)
        col1.metric("Saldo Kas Umum", format_rupiah(ringkasan_kas["Kas Umum"]["saldo"]))
        col2.metric("Saldo Kas Proker", format_rupiah(ringkasan_kas["Kas Proker"]["saldo"]))
        col3.metric("Total Keseluruhan", format_rupiah(ringkasan_kas["Total"]["saldo"]))

        tampil = df_laporan.copy()
        tampil["Tanggal"] = tampil["Tanggal"].dt.strftime("%d-%m-%Y")
        tampil["Jumlah"] = tampil["Jumlah"].apply(format_rupiah)
        st.dataframe(
            tampil[["ID", "Tanggal", "Jenis", "Kas", "Proker", "Kategori", "Keterangan", "Jumlah"]],
            width="stretch", hide_index=True,
        )

        theme.divider()
        st.subheader("⬇️ Unduh Laporan")

        filter_info = f"Periode: {tgl_mulai.strftime('%d-%m-%Y')} s/d {tgl_akhir.strftime('%d-%m-%Y')}"
        if filter_kas:
            filter_info += f" | Kas: {', '.join(filter_kas)}"
        if filter_proker:
            filter_info += f" | Proker: {', '.join(filter_proker)}"

        colA, colB = st.columns(2)
        with colA:
            excel_bytes = generate_excel(df_laporan)
            st.download_button(
                "📥 Unduh Excel (.xlsx)",
                data=excel_bytes,
                file_name=f"laporan_keuangan_kkn_{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch",
            )
        with colB:
            pdf_bytes = generate_pdf(df_laporan, filter_info)
            st.download_button(
                "📥 Unduh PDF",
                data=pdf_bytes,
                file_name=f"laporan_keuangan_kkn_{date.today().isoformat()}.pdf",
                mime="application/pdf",
                width="stretch",
            )
