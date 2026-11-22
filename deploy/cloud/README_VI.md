# DACN — Cloud Automation Kit (AWS EC2, 17/11/2026)

**Thiết kế**: Ansible chạy trên WSL (control node), kết nối qua SSH đến AWS EC2 (managed node). Docker và Python validator được chạy **trên EC2**, không trên Docker Desktop tại laptop.

**Kit chỉ bổ sung** `deploy/cloud/` vào repo LMS. Không ghi đè `deploy/validate_deployment.py` hay playbooks Local Staging.

## Cấu trúc

- `deploy/cloud/last_known_good_cloud.json`: stable LMS v2 và Cloud site.
- `deploy/cloud/target_release_cloud.json`: mặc định cùng stable; không tự kích hoạt deployment.
- `deploy/cloud/validate_cloud.py`: validator mở rộng, kiểm tra digest, 6 container app, image ID, MariaDB, Redis, apps và HTTP.
- `deploy/cloud/validate_cloud.yml`: chạy validator trên EC2 qua SSH, chỉ thay đổi/copy 2 Python files trong thư mục automation; **không sửa Compose, containers, dữ liệu**.
- `deploy/cloud/deploy_cloud.yml`: playbook triển khai candidate và rollback có guard; **chưa chạy ngay**.

## Pha A — Chỉ kiểm tra Stable Cloud (chạy trước)

1. Giải nén kit từ WSL vào `~/DACN/SP2/frappe_docker/development/frappe-bench/apps/lms`.
2. Kiểm tra file mới `ls deploy/cloud/` và `git status --short`.
3. Tại WSL, cập nhật IP công cộng mới nhất từ AWS Console, không mặc định dùng IP cũ:

```bash
cd ~/DACN/SP2/frappe_docker/development/frappe-bench/apps/lms
EC2_IP='NHAP_PUBLIC_IPV4_HIEN_TAI'
ANSIBLE="$HOME/DACN/SP2/ansible-venv/bin/ansible-playbook"
"$ANSIBLE" --version
ssh -o IdentitiesOnly=yes -i "$HOME/.ssh/dacn-frappe-lms-key.pem" "ubuntu@$EC2_IP" 'echo SSH_TO_EC2_PASS'
```

4. Chạy playbook validation, không chạy `deploy_cloud.yml`:

```bash
"$ANSIBLE" -i "$EC2_IP," -u ubuntu \
  --private-key "$HOME/.ssh/dacn-frappe-lms-key.pem" \
  -e '{"ansible_ssh_common_args":"-o IdentitiesOnly=yes -o ServerAliveInterval=30 -o ServerAliveCountMax=3"}' \
  deploy/cloud/validate_cloud.yml
```

Kết quả mong đợi: `CLOUD DEPLOYMENT VALIDATION: PASS` và recap `failed=0`. Các thành phần kiểm tra: stable digest v2, 6 application services, image ID thực chạy, MariaDB healthy, 2 Redis PONG, frappe/payments/lms, HTTP 200.

> Để tránh làm lộ mật khẩu: KHÔNG hiển thị `cloud.env`, `site_config.json`, private key hoặc PAT khi gửi log.

## Pha B — Chỉ sau khi chuẩn bị candidate image và phê duyệt

`deploy_cloud.yml` mặc định sẽ **từ chối** chạy nếu không có `-e cloud_deploy_approved=true`; ngoài ra yêu cầu target khác stable, candidate đã tồn tại trên EC2, backup DB hiện diện, stable baseline phải PASS. Nó chỉ chạy Compose trên `configurator` và sáu service `backend, frontend, websocket, queue-short, queue-long, scheduler`, không thay đổi db/redis và không xóa volumes. Candidate fail sẽ chạy block `rescue` để trở về stable.

### Cảnh báo vận hành

- Bản backup hiện ở cùng EBS EC2, không phải bản sao off-instance và **chưa restore thử**. Sao lưu ra ngoài EC2 trước khi làm thử nghiệm có rủi ro cao.
- Ansible `rescue` **không được bảo đảm kích hoạt khi mất kết nối SSH hoặc máy EC2 unreachable**. Nếu mất mạng giữa deployment cần kiểm tra và phục hồi thủ công. Xem tài liệu Ansible blocks.
- `--pull never`: candidate image phải tải hoặc build xong trên EC2 trước khi thử.
- Dòng `CUSTOM_TAG` trong `cloud.env` chỉ được thay đổi khi thực hiện deployment có guard; DB_PASSWORD giữ nguyên.
- Không dùng `docker compose down -v`, `docker volume prune`, `docker system prune -a`, không chạy `bench new-site` lại.
- Khối `rescue` đánh dấu playbook FAIL có chủ đích sau thông điệp `ROLLBACK VERIFIED`; phân biệt với lỗi rollback không hoàn tất.
- Khi một candidate thật được duyệt và triển khai thành công, metadata `last_known_good_cloud.json` cần được cập nhật/promotion sau khi review, không thực hiện tự động.

**Chưa được kiểm thử trên EC2 thực trong môi trường tác giả**: Bộ file đã được kiểm tra cú pháp Python và cấu trúc YAML offline. Bạn phải xác nhận Pha A PASS trước khi chạy Pha B trên EC2.
