# Triển khai và kiểm chứng Cloud (cập nhật 22/11/2026)

Thư mục này chứa mã triển khai Frappe LMS trên AWS EC2. [README chính](../../README.md) mô tả toàn bộ chu trình phát hành. Tài liệu này thay thế ghi chú chuẩn bị ngày 17/11, vốn được viết trước khi hoàn tất tích hợp Jenkins.

## Thành phần

- last_known_good_cloud.json và target_release_cloud.json: image tag, digest, site và URL kiểm tra cục bộ được quản lý bằng pull request. Hiện hai tệp cùng trỏ tới bản đã được Jenkins #16 kiểm chứng và PR #6 ghi nhận.
- deploy_cloud.yml: Ansible kiểm tra trước triển khai, tải image từ GHCR theo digest đã duyệt, triển khai các dịch vụ ứng dụng, xác minh và rollback riêng image.
- validate_cloud.py: kiểm tra digest, image ID thực chạy, sáu dịch vụ ứng dụng, MariaDB, hai Redis, danh sách ứng dụng và HTTP 200.
- validate_cloud.yml: chạy kiểm tra trạng thái trên EC2; ngoài việc chép hai tập lệnh validator vào thư mục automation, không thay đổi Compose hay dữ liệu.

## Quy trình phát hành

1. Chạy thủ công [DACN CI - Frappe Tests](../../.github/workflows/dacn-frappe-tests.yml) trên nhánh main với build_and_smoke=true. Lấy run ID, commit và image digest từ run thành công cùng release manifest.
2. Chạy job Jenkins dacn-release-digest từ nhánh main, điền GHA_RUN_ID mới và EC2_HOST hiện tại. So sánh commit, run ID và digest mà Jenkins xác minh với GitHub Actions trước khi bấm Approve. Nếu GHA_RUN_ID trống, job chỉ chạy kiểm thử digest.
3. Sau phê duyệt, Jenkins cấp credential GHCR quyền đọc cho Ansible. Playbook kiểm tra bản stable và tính toàn vẹn backup, đăng nhập bằng Docker config tạm, tải đúng digest, gắn tag và xóa Docker config tạm.
4. Playbook tạo lại configurator và sáu dịch vụ ứng dụng, rồi chạy validator. Nếu kiểm chứng thất bại, khối rescue đưa **image ứng dụng** về bản last-known-good và kiểm tra lại. Khối này không restore cơ sở dữ liệu.
5. Chỉ sau khi có RELEASE ACCEPTED và một lần kiểm tra validator độc lập đạt PASS, cập nhật cả hai JSON về tag và digest đã kiểm chứng qua pull request. Promotion vẫn là thao tác thủ công. Chạy lại candidate đã là stable sẽ bị từ chối.

## Bằng chứng ngày 22/11/2026

- GitHub Actions run 44930522016; commit b3f715564bab025185dea6fbf65e48665e95236a; digest sha256:dc672fce92ad7a8c4107c3991c15a74c4778afd63bd9a4767c6afa6783307bd5.
- Jenkins #16: phê duyệt thủ công, tải image theo digest trên EC2, RELEASE ACCEPTED, SUCCESS; recap ok=29, failed=0, unreachable=0, rescued=0.
- Validator chạy độc lập trên EC2: sáu dịch vụ có image ID khớp, MariaDB healthy, hai Redis PONG, ứng dụng frappe/payments/lms và HTTP 200; kết luận CLOUD DEPLOYMENT VALIDATION: PASS.
- PR #6 cập nhật metadata stable và target. Run #16 không kích hoạt nhánh rescue.

## Phạm vi và giới hạn

- Cổng kiểm tra backup yêu cầu có tệp DB nén hợp lệ qua gzip -t. Backup trong thí nghiệm nằm trên EBS của EC2; chưa chứng minh restore từ bản sao nằm ngoài máy.
- Ansible rescue không bảo đảm chạy nếu SSH hoặc EC2 mất kết nối. Tình huống đó cần kiểm tra và khôi phục thủ công.
- Metadata Cloud không chứa cloud.env, khóa SSH riêng hay token GHCR. URL 127.0.0.1:8200 là loopback trên EC2, không phải địa chỉ demo công khai.
- Không dọn Docker volume hoặc tạo lại site trong quy trình cập nhật riêng image.
