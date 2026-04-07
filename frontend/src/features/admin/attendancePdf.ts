import notoSansRegularUrl from "@/assets/fonts/NotoSans-Regular.ttf?url";
import i18n from "@/i18n";
import { getIntlLocale, getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatStateLabel, formatTime } from "@/shared/presentation";
import type { AttendanceSessionDetails } from "@/types/domain";

const PDF_FONT_FAMILY = "NotoSansPdf";
const PDF_FONT_FILE = "NotoSans-Regular.ttf";

let pdfFontBinaryPromise: Promise<string> | null = null;

function buildSeatKey(row: number, seatNumber: number): string {
  return `${row}-${seatNumber}`;
}

function formatPercent(value: number, language: string): string {
  return new Intl.NumberFormat(getIntlLocale(language), {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPdfDateTime(value: string, language: string): string {
  return new Intl.DateTimeFormat(getIntlLocale(language), {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function sanitizeFileSegment(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/gi, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 48);
}

function arrayBufferToBinaryString(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const chunkSize = 0x8000;
  let binary = "";

  for (let index = 0; index < bytes.length; index += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(index, index + chunkSize));
  }

  return binary;
}

async function getPdfFontBinary(): Promise<string> {
  if (!pdfFontBinaryPromise) {
    pdfFontBinaryPromise = fetch(notoSansRegularUrl)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to load embedded PDF font: ${response.status}`);
        }

        return response.arrayBuffer();
      })
      .then(arrayBufferToBinaryString);
  }

  return pdfFontBinaryPromise;
}

async function registerPdfFont(doc: InstanceType<(typeof import("jspdf"))["jsPDF"]>): Promise<void> {
  const fontBinary = await getPdfFontBinary();
  doc.addFileToVFS(PDF_FONT_FILE, fontBinary);
  doc.addFont(PDF_FONT_FILE, PDF_FONT_FAMILY, "normal");
  doc.addFont(PDF_FONT_FILE, PDF_FONT_FAMILY, "bold");
  doc.setFont(PDF_FONT_FAMILY, "normal");
}

function fitText(doc: InstanceType<(typeof import("jspdf"))["jsPDF"]>, value: string, maxWidth: number): string {
  if (doc.getTextWidth(value) <= maxWidth) {
    return value;
  }

  const ellipsis = "...";
  let result = value;

  while (result.length > 1 && doc.getTextWidth(`${result}${ellipsis}`) > maxWidth) {
    result = result.slice(0, -1);
  }

  return `${result}${ellipsis}`;
}

export async function exportAttendanceSessionPdf(details: AttendanceSessionDetails, language: string): Promise<void> {
  const { jsPDF } = await import("jspdf");
  const t = i18n.getFixedT(language);
  const doc = new jsPDF({
    unit: "pt",
    format: "a4",
    compress: true,
  });
  await registerPdfFont(doc);

  const pageWidth = doc.internal.pageSize.getWidth();
  const pageHeight = doc.internal.pageSize.getHeight();
  const marginX = 40;
  const marginTop = 40;
  const marginBottom = 40;
  const contentWidth = pageWidth - marginX * 2;
  const movieTitle = getLocalizedText(details.session.movie.title, language);
  const reportDate = formatPdfDateTime(details.generated_at, language);
  const occupiedSeatKeys = new Set(
    details.occupied_tickets.map((ticket) => buildSeatKey(ticket.seat_row, ticket.seat_number)),
  );
  const groupedRows = new Map<number, number[]>();

  for (const seat of details.seat_map.seats) {
    const currentRow = groupedRows.get(seat.row) ?? [];
    currentRow.push(seat.number);
    groupedRows.set(seat.row, currentRow);
  }
  const sortedRows = Array.from(groupedRows.entries()).sort((left, right) => left[0] - right[0]);

  let y = marginTop;

  function ensureSpace(height: number, repeatHeader?: () => void) {
    if (y + height <= pageHeight - marginBottom) {
      return;
    }

    doc.addPage();
    y = marginTop;
    if (repeatHeader) {
      repeatHeader();
    }
  }

  function drawSectionHeading(title: string, subtitle?: string) {
    ensureSpace(subtitle ? 46 : 28);
    doc.setTextColor(214, 188, 155);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(10);
    doc.text(title, marginX, y);
    y += 16;

    if (subtitle) {
      doc.setTextColor(88, 96, 112);
      doc.setFont(PDF_FONT_FAMILY, "normal");
      doc.setFontSize(10);
      doc.text(subtitle, marginX, y);
      y += 18;
    }
  }

  const titleX = marginX + 22;
  const titleMaxWidth = contentWidth - 44;
  const sessionMetaLine = `${formatPdfDateTime(details.session.start_time, language)} | ${formatTime(details.session.start_time, language)}-${formatTime(details.session.end_time, language)} | ${formatStateLabel(details.session.status)}`;
  const generatedLine = t("admin.reports.attendanceDetail.generatedLabel", { date: reportDate });

  doc.setFont(PDF_FONT_FAMILY, "bold");
  doc.setFontSize(24);
  const titleLines = doc.splitTextToSize(movieTitle, titleMaxWidth);
  const titleLineHeight = 24 * doc.getLineHeightFactor();
  const titleBlockHeight = Math.max(titleLines.length, 1) * titleLineHeight;

  doc.setFont(PDF_FONT_FAMILY, "normal");
  doc.setFontSize(11);
  const metaLines = doc.splitTextToSize(sessionMetaLine, titleMaxWidth);
  const generatedLines = doc.splitTextToSize(generatedLine, titleMaxWidth);
  const metaLineHeight = 11 * doc.getLineHeightFactor();
  const headerHeight = Math.max(
    112,
    32 + titleBlockHeight + 10 + metaLines.length * metaLineHeight + 6 + generatedLines.length * metaLineHeight + 18,
  );

  doc.setFillColor(17, 21, 29);
  doc.roundedRect(marginX, y, contentWidth, headerHeight, 20, 20, "F");
  doc.setTextColor(214, 188, 155);
  doc.setFont(PDF_FONT_FAMILY, "bold");
  doc.setFontSize(11);
  doc.text(t("admin.reports.attendanceDetail.pdf.title"), titleX, y + 24);

  doc.setTextColor(246, 241, 233);
  doc.setFont(PDF_FONT_FAMILY, "bold");
  doc.setFontSize(24);
  doc.text(titleLines, titleX, y + 52);

  doc.setTextColor(189, 196, 210);
  doc.setFont(PDF_FONT_FAMILY, "normal");
  doc.setFontSize(11);
  const metaY = y + 52 + titleBlockHeight + 6;
  doc.text(metaLines, titleX, metaY);
  doc.text(generatedLines, titleX, metaY + metaLines.length * metaLineHeight + 6);
  y += headerHeight + 28;

  drawSectionHeading(
    t("admin.reports.attendanceDetail.pdf.summaryTitle"),
    t("admin.reports.attendanceDetail.pdf.summarySubtitle"),
  );

  const summaryCards = [
    {
      label: t("common.labels.ticketsSold"),
      value: String(details.tickets_sold),
      detail: t("admin.reports.attendance.soldOfTotal", {
        sold: details.tickets_sold,
        total: details.session.total_seats,
      }),
    },
    {
      label: t("common.labels.availableSeats"),
      value: String(details.seat_map.available_seats),
      detail: t("admin.reports.attendanceDetail.summary.availableDetail"),
    },
    {
      label: t("admin.reports.attendance.capacity"),
      value: String(details.session.total_seats),
      detail: t("admin.reports.attendanceDetail.summary.capacityDetail"),
    },
    {
      label: t("admin.reports.attendance.fillRate"),
      value: formatPercent(details.attendance_rate, language),
      detail: t("admin.reports.attendanceDetail.summary.fillRateDetail"),
    },
    {
      label: t("common.labels.price"),
      value: formatCurrency(details.session.price, language),
      detail: t("admin.reports.attendanceDetail.summary.priceDetail"),
    },
    {
      label: t("common.labels.status"),
      value: formatStateLabel(details.session.status),
      detail: t("admin.reports.attendanceDetail.hallLayout", {
        rows: details.seat_map.rows_count,
        seats: details.seat_map.seats_per_row,
      }),
    },
  ];

  const cardGap = 12;
  const cardWidth = (contentWidth - cardGap) / 2;
  const cardHeight = 58;

  summaryCards.forEach((card, index) => {
    const column = index % 2;
    const row = Math.floor(index / 2);
    const cardX = marginX + column * (cardWidth + cardGap);
    const cardY = y + row * (cardHeight + cardGap);

    doc.setFillColor(246, 243, 238);
    doc.setDrawColor(224, 229, 236);
    doc.roundedRect(cardX, cardY, cardWidth, cardHeight, 14, 14, "FD");
    doc.setTextColor(96, 103, 116);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(9);
    doc.text(card.label, cardX + 14, cardY + 16);
    doc.setTextColor(25, 31, 43);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(18);
    doc.text(card.value, cardX + 14, cardY + 36);
    doc.setTextColor(96, 103, 116);
    doc.setFont(PDF_FONT_FAMILY, "normal");
    doc.setFontSize(8.5);
    doc.text(fitText(doc, card.detail, cardWidth - 28), cardX + 14, cardY + 50);
  });
  y += Math.ceil(summaryCards.length / 2) * (cardHeight + cardGap) + 8;

  drawSectionHeading(
    t("admin.reports.attendanceDetail.pdf.seatMapTitle"),
    t("admin.reports.attendanceDetail.seatMap.intro"),
  );

  const labelWidth = 28;
  const seatGap = 5;
  const rowGap = 8;
  const seatSize = Math.min(
    18,
    Math.floor(
      (contentWidth - 48 - labelWidth * 2 - seatGap * (details.seat_map.seats_per_row - 1)) /
        details.seat_map.seats_per_row,
    ),
  );
  const rowWidth =
    labelWidth * 2 +
    details.seat_map.seats_per_row * seatSize +
    (details.seat_map.seats_per_row - 1) * seatGap;
  const mapStartX = marginX + (contentWidth - rowWidth) / 2;
  const renderedRowCount = sortedRows.length;
  const rowsHeight =
    renderedRowCount > 0 ? renderedRowCount * seatSize + (renderedRowCount - 1) * rowGap : seatSize;
  const mapTopOffset = 64;
  const legendTopOffset = 18;
  const legendHeight = 12;
  const seatMapCardHeight = Math.max(194, mapTopOffset + rowsHeight + legendTopOffset + legendHeight + 20);

  ensureSpace(seatMapCardHeight + 20);
  const mapStartY = y + mapTopOffset;
  const legendY = mapStartY + rowsHeight + legendTopOffset;
  doc.setFillColor(244, 246, 249);
  doc.setDrawColor(224, 229, 236);
  doc.roundedRect(marginX, y, contentWidth, seatMapCardHeight, 18, 18, "FD");

  doc.setFillColor(255, 255, 255);
  doc.setDrawColor(214, 219, 229);
  doc.roundedRect(marginX + 24, y + 20, contentWidth - 48, 10, 10, 10, "FD");
  doc.setTextColor(174, 132, 74);
  doc.setFont(PDF_FONT_FAMILY, "bold");
  doc.setFontSize(8);
  doc.text(t("booking.seatMap.screen"), pageWidth / 2, y + 46, { align: "center" });

  doc.setFont(PDF_FONT_FAMILY, "bold");
  doc.setFontSize(7.5);

  sortedRows.forEach(([rowNumber, seatNumbers], rowIndex) => {
    const rowY = mapStartY + rowIndex * (seatSize + rowGap);

    doc.setTextColor(96, 103, 116);
    doc.text(`${rowNumber}`, mapStartX + 10, rowY + seatSize - 5);
    doc.text(`${rowNumber}`, mapStartX + rowWidth - 10, rowY + seatSize - 5, { align: "right" });

    seatNumbers
      .sort((left, right) => left - right)
      .forEach((seatNumber, seatIndex) => {
        const seatKey = buildSeatKey(rowNumber, seatNumber);
        const seatX = mapStartX + labelWidth + seatIndex * (seatSize + seatGap);
        const occupied = occupiedSeatKeys.has(seatKey);

        if (occupied) {
          doc.setFillColor(228, 139, 90);
          doc.setDrawColor(197, 111, 66);
          doc.setTextColor(46, 23, 10);
        } else {
          doc.setFillColor(212, 225, 219);
          doc.setDrawColor(170, 197, 185);
          doc.setTextColor(42, 66, 56);
        }

        doc.roundedRect(seatX, rowY, seatSize, seatSize, 5, 5, "FD");
        doc.text(String(seatNumber), seatX + seatSize / 2, rowY + seatSize / 2 + 2, { align: "center" });
      });
  });

  const legendItems = [
    { label: t("booking.seatMap.legend.available"), color: [212, 225, 219] as const, border: [170, 197, 185] as const },
    { label: t("booking.seatMap.legend.occupied"), color: [228, 139, 90] as const, border: [197, 111, 66] as const },
  ];
  let legendX = marginX + 28;

  doc.setFont(PDF_FONT_FAMILY, "normal");
  doc.setFontSize(9);
  legendItems.forEach((item) => {
    doc.setFillColor(item.color[0], item.color[1], item.color[2]);
    doc.setDrawColor(item.border[0], item.border[1], item.border[2]);
    doc.roundedRect(legendX, legendY, 12, 12, 3, 3, "FD");
    doc.setTextColor(88, 96, 112);
    doc.text(item.label, legendX + 18, legendY + 10);
    legendX += 18 + doc.getTextWidth(item.label) + 26;
  });

  y += seatMapCardHeight + 20;

  ensureSpace(details.occupied_tickets.length === 0 ? 94 : 118);
  drawSectionHeading(
    t("admin.reports.attendanceDetail.pdf.buyersTitle"),
    t("admin.reports.attendanceDetail.buyers.results", { count: details.occupied_tickets.length }),
  );

  const columns = [
    { label: t("common.labels.seat"), width: 40 },
    { label: t("common.labels.name"), width: 82 },
    { label: t("common.labels.email"), width: 128 },
    { label: t("admin.reports.attendanceDetail.table.purchasedAt"), width: 94 },
    { label: t("admin.reports.attendanceDetail.table.ticketStatus"), width: 68 },
    { label: t("admin.reports.attendanceDetail.table.orderStatus"), width: 68 },
  ] as const;
  const rowHeight = 24;

  const drawTableHeader = () => {
    doc.setFillColor(26, 31, 40);
    doc.rect(marginX, y, contentWidth, rowHeight, "F");
    doc.setTextColor(244, 246, 249);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(9);

    let cursorX = marginX + 10;
    columns.forEach((column) => {
      doc.text(column.label, cursorX, y + 15);
      cursorX += column.width;
    });
    y += rowHeight;
  };

  if (details.occupied_tickets.length === 0) {
    ensureSpace(48);
    doc.setTextColor(88, 96, 112);
    doc.setFont(PDF_FONT_FAMILY, "normal");
    doc.setFontSize(10);
    doc.text(t("admin.reports.attendanceDetail.buyers.emptyText"), marginX, y + 12);
    y += 24;
  } else {
    ensureSpace(rowHeight, drawTableHeader);
    drawTableHeader();

    details.occupied_tickets.forEach((ticket, index) => {
      ensureSpace(rowHeight, drawTableHeader);
      doc.setFillColor(index % 2 === 0 ? 250 : 244, index % 2 === 0 ? 252 : 246, index % 2 === 0 ? 255 : 249);
      doc.setDrawColor(228, 232, 238);
      doc.rect(marginX, y, contentWidth, rowHeight, "FD");
      doc.setTextColor(40, 46, 58);
      doc.setFont(PDF_FONT_FAMILY, "normal");
      doc.setFontSize(8.5);

      const values = [
        buildSeatKey(ticket.seat_row, ticket.seat_number),
        ticket.user_name || t("admin.reports.attendanceDetail.buyers.buyerFallback"),
        ticket.user_email || "-",
        formatPdfDateTime(ticket.purchased_at, language),
        formatStateLabel(ticket.status),
        ticket.order_status ? formatStateLabel(ticket.order_status) : t("admin.reports.attendanceDetail.buyers.noOrderStatus"),
      ];

      let cursorX = marginX + 10;
      values.forEach((value, valueIndex) => {
        const columnWidth = columns[valueIndex].width - 12;
        doc.text(fitText(doc, value, columnWidth), cursorX, y + 15);
        cursorX += columns[valueIndex].width;
      });
      y += rowHeight;
    });
  }

  ensureSpace(24);
  doc.setTextColor(112, 118, 132);
  doc.setFont(PDF_FONT_FAMILY, "normal");
  doc.setFontSize(8);
  doc.text(
    t("admin.reports.attendanceDetail.pdf.generatedAt", { date: reportDate }),
    marginX,
    y + 16,
  );

  const fileName = `${sanitizeFileSegment(t("admin.reports.attendanceDetail.pdf.fileNamePrefix")) || "attendance"}-${sanitizeFileSegment(movieTitle) || "session"}.pdf`;
  doc.save(fileName);
}
