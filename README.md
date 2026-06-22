# VNScreener SEPA/VCP Stock Screener

Ứng dụng lọc cổ phiếu Việt Nam (HOSE, HNX, UPCoM) áp dụng các tiêu chí kỹ thuật và cơ bản nâng cao theo phương pháp **SEPA/VCP của Mark Minervini**.

## Các chức năng chính
1. **Trend Template:** Lọc cổ phiếu có xu hướng tăng dài hạn mạnh mẽ ($Giá > MA20 > MA50 > MA200$ và các đường MA đang hướng lên).
2. **Relative Strength (RS) vs VNINDEX:** Tính điểm sức mạnh tương quan để tìm cổ phiếu mạnh nhất thị trường.
3. **Nền giá tích lũy chặt & Mô hình VCP:** Đo lường độ siết chặt biến động giá và cấu trúc co hẹp.
4. **Volume cạn kiệt:** Phát hiện cạn cung tại khu vực tích lũy.
5. **Đếm phiên phân phối:** Theo dõi áp lực bán tháo trong 20 phiên gần nhất.
6. **Tín hiệu Điểm mua (Breakout & Pullback):** Phát hiện các điểm bứt phá hoặc kiểm định lại nông và hồi phục nhanh.

---

## Hướng dẫn Chạy cục bộ trên Máy tính (Windows)

Để chạy thử nghiệm giao diện Desktop (y hệt như giao diện trên điện thoại):

1. **Mở PowerShell/Terminal** và di chuyển vào thư mục dự án:
   ```powershell
   cd C:\Users\sol\.gemini\antigravity-ide\scratch\VietnamStockScreener
   ```

2. **Cài đặt các thư viện cần thiết** (nếu chưa cài):
   ```powershell
   pip install -r requirements.txt
   ```

3. **Chạy ứng dụng:**
   ```powershell
   python main.py
   ```
   *Một cửa sổ ứng dụng desktop hiện đại sẽ mở ra.*

---

## Hướng dẫn tự động Đóng gói APK sang Điện thoại Android

Để có ứng dụng (.apk) cài trên điện thoại mà không cần cài đặt môi trường Android SDK phức tạp trên máy tính của bạn:

1. **Đưa mã nguồn lên GitHub:**
   - Tạo một repository mới trên GitHub (ví dụ: `vietnam-stock-screener`).
   - Đẩy toàn bộ thư mục `VietnamStockScreener` này lên GitHub.
   
2. **Kích hoạt GitHub Actions:**
   - File cấu hình đã được viết sẵn trong thư mục `.github/workflows/build_apk.yml`.
   - Mỗi lần bạn đẩy mã nguồn lên GitHub (hoặc kích hoạt thủ công trong mục Actions), GitHub sẽ tự động biên dịch và tạo ra file APK.

3. **Tải file APK về điện thoại:**
   - Vào kho lưu trữ của bạn trên website GitHub.
   - Chọn tab **Actions**.
   - Bấm vào lần chạy build gần nhất (ví dụ: "Build Flet APK").
   - Kéo xuống phần **Artifacts** ở cuối trang, click vào **VNScreener-APK** để tải file zip chứa ứng dụng về.
   - Giải nén và cài đặt file `.apk` vào điện thoại Android của bạn!
