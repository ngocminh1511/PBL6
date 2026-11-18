import type { ChatMessage, ChatSession } from './types';

/**
 * Xuất báo cáo PDF trực tiếp cho ngữ cảnh phiên làm việc hiện tại
 * bằng cách tạo tài liệu in ấn chuẩn A4 và kích hoạt hộp thoại in / lưu PDF của trình duyệt.
 */
export function exportSessionToPDF(
  session: ChatSession | undefined,
  sessionId: string | null,
  messages: ChatMessage[]
) {
  if (!messages || messages.length === 0) {
    alert('Phiên làm việc hiện tại chưa có nội dung trao đổi để xuất báo cáo.');
    return;
  }

  const title = session?.title || 'Phiên tra cứu pháp luật';
  const timeStr = new Date().toLocaleString('vi-VN');
  const domainText = session?.domain === 'lao_dong'
    ? 'Pháp luật Lao động'
    : session?.domain === 'bhxh'
    ? 'Bảo hiểm Xã hội & Y tế'
    : 'Toàn bộ kho số hóa (Tổng hợp)';

  // Xây dựng danh sách các lượt hỏi & đáp
  let conversationHtml = '';
  let turnIndex = 1;

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role === 'user') {
      const assistantMsg = messages.slice(i + 1).find(m => m.role === 'assistant');
      
      let evidenceHtml = '';
      if (assistantMsg?.legal_evidence && assistantMsg.legal_evidence.length > 0) {
        evidenceHtml = `
          <div class="evidence-box">
            <h4 class="evidence-title">📚 CĂN CỨ PHÁP LÝ TRÍCH DẪN & ĐỐI CHIẾU:</h4>
            <table class="evidence-table">
              <thead>
                <tr>
                  <th style="width: 25%;">Điều / Khoản / Điểm</th>
                  <th style="width: 35%;">Văn bản / Đề mục Pháp điển</th>
                  <th style="width: 40%;">Nội dung trích yếu</th>
                </tr>
              </thead>
              <tbody>
                ${assistantMsg.legal_evidence.map(e => `
                  <tr>
                    <td><strong>${escapeHtml(e.citation || '—')}</strong></td>
                    <td>${escapeHtml(e.meta_de_muc || e.ten || e.source || 'Bộ Pháp điển điện tử')}</td>
                    <td class="text-source">${escapeHtml(e.text ? (e.text.length > 250 ? e.text.slice(0, 250) + '...' : e.text) : '—')}</td>
                  </tr>
                `).join('')}
              </tbody>
            </table>
          </div>
        `;
      }

      conversationHtml += `
        <div class="turn-card">
          <div class="turn-header">
            <span class="turn-badge">LƯỢT TRA CỨU #${turnIndex}</span>
            <span class="turn-time">${new Date(msg.created_at).toLocaleTimeString('vi-VN', { hour: '2-digit', minute: '2-digit' })}</span>
          </div>

          <div class="question-section">
            <p class="section-label">❓ CÂU HỎI TÌNH HUỐNG / YÊU CẦU TRA CỨU:</p>
            <div class="question-content">${escapeHtml(msg.content)}</div>
          </div>

          ${assistantMsg ? `
            <div class="answer-section">
              <p class="section-label">⚖️ KẾT QUẢ TƯ VẤN & TRẢ LỜI CỦA TRỢ LÝ PHÁP LÝ:</p>
              <div class="answer-content">${formatAnswerContent(assistantMsg.content)}</div>
            </div>
            ${evidenceHtml}
          ` : '<p style="color: #666; font-style: italic;">(Đang chờ phản hồi...)</p>'}
        </div>
      `;
      turnIndex++;
    }
  }

  const printableHtml = `
<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <title>Báo cáo tra cứu pháp luật - ${escapeHtml(title)}</title>
  <style>
    @page {
      size: A4;
      margin: 15mm 15mm 20mm 15mm;
    }
    * {
      box-sizing: border-box;
      -webkit-print-color-adjust: exact !important;
      print-color-adjust: exact !important;
    }
    body {
      font-family: "Times New Roman", Times, serif;
      color: #1a1a1a;
      line-height: 1.5;
      font-size: 13pt;
      margin: 0;
      padding: 0;
      background: #fff;
    }
    .header-gov {
      text-align: center;
      margin-bottom: 25px;
    }
    .gov-title {
      font-size: 12pt;
      font-weight: bold;
      text-transform: uppercase;
      margin: 0 0 4px 0;
      letter-spacing: 0.5px;
    }
    .gov-subtitle {
      font-size: 12pt;
      font-weight: bold;
      margin: 0 0 8px 0;
    }
    .gov-divider {
      width: 140px;
      height: 1.5px;
      background: #111;
      margin: 0 auto 20px auto;
    }
    .report-main-title {
      font-size: 16pt;
      font-weight: bold;
      text-transform: uppercase;
      color: #0d47a1;
      margin: 0 0 6px 0;
      text-align: center;
    }
    .report-sub {
      font-size: 11pt;
      color: #555;
      font-style: italic;
      text-align: center;
      margin: 0 0 20px 0;
    }
    .meta-box {
      border: 1px solid #c5cae9;
      background-color: #f8faff;
      border-radius: 6px;
      padding: 12px 16px;
      margin-bottom: 25px;
      font-size: 11.5pt;
    }
    .meta-row {
      margin-bottom: 6px;
    }
    .meta-row:last-child {
      margin-bottom: 0;
    }
    .turn-card {
      border: 1px solid #d1d5db;
      border-radius: 8px;
      padding: 16px;
      margin-bottom: 22px;
      page-break-inside: avoid;
      background: #ffffff;
    }
    .turn-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      border-bottom: 1px solid #e5e7eb;
      padding-bottom: 8px;
      margin-bottom: 12px;
    }
    .turn-badge {
      font-weight: bold;
      font-size: 11pt;
      color: #1e3a8a;
      letter-spacing: 0.5px;
    }
    .turn-time {
      font-size: 10pt;
      color: #6b7280;
    }
    .section-label {
      font-weight: bold;
      font-size: 11pt;
      color: #374151;
      margin: 0 0 6px 0;
    }
    .question-section {
      background: #f3f4f6;
      border-left: 4px solid #3b82f6;
      padding: 10px 14px;
      border-radius: 4px;
      margin-bottom: 14px;
    }
    .question-content {
      font-size: 12.5pt;
      color: #111827;
      font-weight: 500;
    }
    .answer-section {
      margin-bottom: 14px;
    }
    .answer-content {
      font-size: 12pt;
      line-height: 1.6;
      color: #1f2937;
      text-align: justify;
    }
    .evidence-box {
      margin-top: 14px;
      background: #fafafa;
      border: 1px solid #e5e7eb;
      border-radius: 6px;
      padding: 10px 12px;
    }
    .evidence-title {
      font-size: 10.5pt;
      color: #1e40af;
      margin: 0 0 8px 0;
      text-transform: uppercase;
    }
    .evidence-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 10.5pt;
    }
    .evidence-table th, .evidence-table td {
      border: 1px solid #d1d5db;
      padding: 6px 8px;
      text-align: left;
      vertical-align: top;
    }
    .evidence-table th {
      background-color: #f1f5f9;
      font-weight: bold;
    }
    .text-source {
      font-size: 10pt;
      color: #4b5563;
      font-style: italic;
    }
    .footer-note {
      text-align: center;
      font-size: 10pt;
      color: #6b7280;
      font-style: italic;
      margin-top: 30px;
      padding-top: 15px;
      border-top: 1px dashed #d1d5db;
    }
  </style>
</head>
<body>
  <div class="header-gov">
    <p class="gov-title">CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM</p>
    <p class="gov-subtitle">Độc lập - Tự do - Hạnh phúc</p>
    <div class="gov-divider"></div>
    <h1 class="report-main-title">BÁO CÁO KẾT QUẢ TRA CỨU & HỎI ĐÁP PHÁP LUẬT</h1>
    <p class="report-sub">Trích xuất tự động từ hệ thống Pháp luật Việt Nam (Hybrid GraphRAG)</p>
  </div>

  <div class="meta-box">
    <div class="meta-row"><strong>• Tên phiên tra cứu:</strong> ${escapeHtml(title)}</div>
    <div class="meta-row"><strong>• Mã phiên (Session ID):</strong> <code>${escapeHtml(sessionId || 'Phiên làm việc hiện tại')}</code></div>
    <div class="meta-row"><strong>• Phạm vi lập luận:</strong> ${escapeHtml(domainText)}</div>
    <div class="meta-row"><strong>• Thời điểm trích xuất:</strong> ${timeStr}</div>
    <div class="meta-row"><strong>• Số lượt câu hỏi đã xử lý:</strong> ${turnIndex - 1} lượt</div>
  </div>

  <div class="content-body">
    ${conversationHtml}
  </div>

  <div class="footer-note">
    Báo cáo này được tạo tự động nhằm mục đích hỗ trợ nghiên cứu, tra cứu pháp luật và đối chiếu quy phạm theo Bộ Pháp điển điện tử.
  </div>
</body>
</html>
  `;

  // Sử dụng iframe ẩn để in trực tiếp, không phụ thuộc popup blocker
  const iframe = document.createElement('iframe');
  iframe.style.position = 'fixed';
  iframe.style.right = '0';
  iframe.style.bottom = '0';
  iframe.style.width = '0';
  iframe.style.height = '0';
  iframe.style.border = '0';
  iframe.setAttribute('title', 'Báo cáo PDF');
  document.body.appendChild(iframe);

  const doc = iframe.contentWindow?.document;
  if (!doc) {
    alert('Không thể khởi tạo trình in PDF trên trình duyệt này.');
    return;
  }

  doc.open();
  doc.write(printableHtml);
  doc.close();

  // Đợi iframe render xong styles rồi kích hoạt window.print()
  setTimeout(() => {
    iframe.contentWindow?.focus();
    iframe.contentWindow?.print();
    setTimeout(() => {
      document.body.removeChild(iframe);
    }, 1500);
  }, 350);
}

function escapeHtml(str: string): string {
  if (!str) return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function formatAnswerContent(content: string): string {
  if (!content) return '';
  // Chuyển markdown cơ bản hoặc ngắt dòng sang HTML
  const escaped = escapeHtml(content);
  return escaped
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n\n/g, '<br/><br/>')
    .replace(/\n/g, '<br/>');
}

