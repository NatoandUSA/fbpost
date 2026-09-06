import { API } from './api.js';
import { showToast } from './toast.js';

export async function stopCurrentJob() {
    try {
        const res = await API.cancelActive();
        showToast(res.message || 'Đã gửi lệnh dừng tiến trình.', res.success ? 'success' : 'error');
        return res;
    } catch (err) {
        showToast('Lỗi khi dừng: ' + err.message, 'error');
        throw err;
    }
}
