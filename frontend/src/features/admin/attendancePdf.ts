import notoSansRegularUrl from "@/assets/fonts/NotoSans-Regular.ttf?url";
import i18n from "@/i18n";
import { getIntlLocale, getLocalizedText } from "@/shared/localization";
import { formatCurrency, formatStateLabel, formatTime } from "@/shared/presentation";
import type { AttendanceSessionDetails } from "@/types/domain";

type AttendanceTicket = AttendanceSessionDetails["occupied_tickets"][number];
type SeatUsageTone = "available" | "notUsed" | "used" | "cancelled";

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

function formatPdfDate(value: string, language: string): string {
  return new Intl.DateTimeFormat(getIntlLocale(language), {
    day: "2-digit",
    month: "short",
    year: "numeric",
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

function isTicketCancelled(ticket: AttendanceTicket): boolean {
  return ticket.status === "cancelled" || Boolean(ticket.cancelled_at);
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
  const ticketBySeatKey = new Map(
    details.occupied_tickets.map((ticket) => [buildSeatKey(ticket.seat_row, ticket.seat_number), ticket]),
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
  const sessionDateLine = `${formatPdfDate(details.session.start_time, language)} | ${formatTime(details.session.start_time, language)}-${formatTime(details.session.end_time, language)}`;

  const getTicketUsageLabel = (ticket: AttendanceTicket): string => {
    if (isTicketCancelled(ticket)) {
      return t("admin.reports.attendanceDetail.usage.cancelled");
    }

    return ticket.checked_in_at
      ? t("admin.reports.attendanceDetail.usage.used")
      : t("admin.reports.attendanceDetail.usage.notUsed");
  };

  const isTicketReadyForEntry = (ticket: AttendanceTicket): boolean =>
    ticket.status === "purchased" &&
    ticket.order_status !== "cancelled" &&
    !ticket.checked_in_at &&
    !isTicketCancelled(ticket) &&
    details.session.status === "scheduled" &&
    new Date(details.session.start_time).getTime() > new Date(details.generated_at).getTime();

  const getTicketUsageDetail = (ticket: AttendanceTicket): string => {
    if (ticket.checked_in_at) {
      return formatPdfDateTime(ticket.checked_in_at, language);
    }

    if (isTicketCancelled(ticket)) {
      return t("admin.reports.attendanceDetail.usage.cancelledDetail");
    }

    return isTicketReadyForEntry(ticket)
      ? t("admin.reports.attendanceDetail.usage.notUsedDetail")
      : t("admin.reports.attendanceDetail.usage.notCheckedInDetail");
  };

  const cancelledTicketsCount = details.occupied_tickets.filter((ticket) => isTicketCancelled(ticket)).length;
  const checkedInTicketsCount = details.occupied_tickets.filter((ticket) => Boolean(ticket.checked_in_at)).length;
  const activeTicketsCount = details.occupied_tickets.length - cancelledTicketsCount;
  const notUsedTicketsCount = details.occupied_tickets.filter(
    (ticket) => !isTicketCancelled(ticket) && !ticket.checked_in_at,
  ).length;
  const validForEntryCount = details.occupied_tickets.filter((ticket) => isTicketReadyForEntry(ticket)).length;
  const uniqueBuyerCount = new Set(details.occupied_tickets.map((ticket) => ticket.user_id)).size;

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
    164,
    32 + titleBlockHeight + 10 + metaLines.length * metaLineHeight + 6 + generatedLines.length * metaLineHeight + 66,
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

  const headerMetrics = [
    { label: t("common.labels.ticketsSold"), value: String(details.tickets_sold) },
    { label: t("admin.reports.attendance.fillRate"), value: formatPercent(details.attendance_rate, language) },
    { label: t("admin.reports.attendanceDetail.summary.checkedIn"), value: String(checkedInTicketsCount) },
    { label: t("common.labels.availableSeats"), value: String(details.seat_map.available_seats) },
  ];
  const headerMetricGap = 10;
  const headerMetricWidth = (titleMaxWidth - headerMetricGap * (headerMetrics.length - 1)) / headerMetrics.length;
  const headerMetricsY = y + headerHeight - 46;

  headerMetrics.forEach((metric, index) => {
    const metricX = titleX + index * (headerMetricWidth + headerMetricGap);
    doc.setFillColor(31, 37, 48);
    doc.setDrawColor(55, 62, 76);
    doc.roundedRect(metricX, headerMetricsY, headerMetricWidth, 30, 8, 8, "FD");
    doc.setTextColor(189, 196, 210);
    doc.setFont(PDF_FONT_FAMILY, "normal");
    doc.setFontSize(7.5);
    doc.text(fitText(doc, metric.label, headerMetricWidth - 14), metricX + 7, headerMetricsY + 11);
    doc.setTextColor(246, 241, 233);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(11);
    doc.text(fitText(doc, metric.value, headerMetricWidth - 14), metricX + 7, headerMetricsY + 24);
  });
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
      label: t("admin.reports.attendance.fillRate"),
      value: formatPercent(details.attendance_rate, language),
      detail: t("admin.reports.attendanceDetail.summary.fillRateDetail"),
    },
    {
      label: t("admin.reports.attendanceDetail.summary.checkedIn"),
      value: String(checkedInTicketsCount),
      detail: t("admin.reports.attendanceDetail.summary.checkedInDetail"),
    },
    {
      label: t("admin.reports.attendanceDetail.summary.notUsed"),
      value: String(notUsedTicketsCount),
      detail: t("admin.reports.attendanceDetail.summary.notUsedDetail"),
    },
    {
      label: t("admin.reports.attendanceDetail.summary.validForEntry"),
      value: String(validForEntryCount),
      detail: t("admin.reports.attendanceDetail.summary.validForEntryDetail"),
    },
    {
      label: t("admin.reports.attendanceDetail.summary.activeTickets"),
      value: String(activeTicketsCount),
      detail: t("admin.reports.attendanceDetail.summary.activeTicketsDetail"),
    },
    {
      label: t("admin.reports.attendanceDetail.summary.uniqueBuyers"),
      value: String(uniqueBuyerCount),
      detail: t("admin.reports.attendanceDetail.summary.uniqueBuyersDetail"),
    },
  ];
  if (cancelledTicketsCount > 0) {
    summaryCards.push({
      label: t("admin.reports.attendanceDetail.summary.cancelledTickets"),
      value: String(cancelledTicketsCount),
      detail: t("admin.reports.attendanceDetail.summary.cancelledTicketsDetail"),
    });
  }

  const cardGap = 12;
  const summaryColumns = 4;
  const cardWidth = (contentWidth - cardGap * (summaryColumns - 1)) / summaryColumns;
  const cardHeight = 66;

  summaryCards.forEach((card, index) => {
    const column = index % summaryColumns;
    const row = Math.floor(index / summaryColumns);
    const cardX = marginX + column * (cardWidth + cardGap);
    const cardY = y + row * (cardHeight + cardGap);

    doc.setFillColor(246, 243, 238);
    doc.setDrawColor(224, 229, 236);
    doc.roundedRect(cardX, cardY, cardWidth, cardHeight, 12, 12, "FD");
    doc.setTextColor(96, 103, 116);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(7.8);
    doc.text(fitText(doc, card.label, cardWidth - 24), cardX + 12, cardY + 15);
    doc.setTextColor(25, 31, 43);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(18);
    doc.text(fitText(doc, card.value, cardWidth - 24), cardX + 12, cardY + 38);
    doc.setTextColor(96, 103, 116);
    doc.setFont(PDF_FONT_FAMILY, "normal");
    doc.setFontSize(7.2);
    doc.text(fitText(doc, card.detail, cardWidth - 24), cardX + 12, cardY + 56);
  });
  y += Math.ceil(summaryCards.length / summaryColumns) * (cardHeight + cardGap) + 8;

  const sessionFacts = [
    `${t("common.labels.dateTime")}: ${sessionDateLine}`,
    `${t("common.labels.status")}: ${formatStateLabel(details.session.status)}`,
    `${t("common.labels.price")}: ${formatCurrency(details.session.price, language)}`,
    `${t("admin.reports.attendance.capacity")}: ${details.session.total_seats}`,
    t("admin.reports.attendanceDetail.hallLayout", {
      rows: details.seat_map.rows_count,
      seats: details.seat_map.seats_per_row,
    }),
  ];

  ensureSpace(44);
  doc.setFillColor(255, 255, 255);
  doc.setDrawColor(224, 229, 236);
  doc.roundedRect(marginX, y, contentWidth, 34, 10, 10, "FD");
  doc.setTextColor(88, 96, 112);
  doc.setFont(PDF_FONT_FAMILY, "normal");
  doc.setFontSize(8.4);
  doc.text(fitText(doc, sessionFacts.join("  |  "), contentWidth - 28), marginX + 14, y + 21);
  y += 50;

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
  const seatUsageStyles: Record<
    SeatUsageTone,
    {
      fill: readonly [number, number, number];
      border: readonly [number, number, number];
      text: readonly [number, number, number];
    }
  > = {
    available: {
      fill: [226, 232, 229],
      border: [188, 203, 196],
      text: [54, 73, 66],
    },
    notUsed: {
      fill: [165, 216, 190],
      border: [99, 170, 134],
      text: [25, 75, 51],
    },
    used: {
      fill: [244, 166, 98],
      border: [204, 116, 55],
      text: [70, 36, 12],
    },
    cancelled: {
      fill: [238, 150, 145],
      border: [197, 82, 76],
      text: [88, 26, 24],
    },
  };
  const getSeatUsageTone = (ticket?: AttendanceTicket): SeatUsageTone => {
    if (!ticket) {
      return "available";
    }

    if (isTicketCancelled(ticket)) {
      return "cancelled";
    }

    return ticket.checked_in_at ? "used" : "notUsed";
  };

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
        const style = seatUsageStyles[getSeatUsageTone(ticketBySeatKey.get(seatKey))];

        doc.setFillColor(style.fill[0], style.fill[1], style.fill[2]);
        doc.setDrawColor(style.border[0], style.border[1], style.border[2]);
        doc.setTextColor(style.text[0], style.text[1], style.text[2]);
        doc.roundedRect(seatX, rowY, seatSize, seatSize, 5, 5, "FD");
        doc.text(String(seatNumber), seatX + seatSize / 2, rowY + seatSize / 2 + 2, { align: "center" });
      });
  });

  const legendItems = [
    { label: t("booking.seatMap.legend.available"), tone: "available" as const },
    { label: t("admin.reports.attendanceDetail.usage.notUsed"), tone: "notUsed" as const },
    { label: t("admin.reports.attendanceDetail.usage.used"), tone: "used" as const },
    { label: t("admin.reports.attendanceDetail.usage.cancelled"), tone: "cancelled" as const },
  ];
  let legendX = marginX + 28;

  doc.setFont(PDF_FONT_FAMILY, "normal");
  doc.setFontSize(9);
  legendItems.forEach((item) => {
    const style = seatUsageStyles[item.tone];
    doc.setFillColor(style.fill[0], style.fill[1], style.fill[2]);
    doc.setDrawColor(style.border[0], style.border[1], style.border[2]);
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
    { label: t("common.labels.seat"), width: 50 },
    { label: t("common.labels.users"), width: 132 },
    { label: t("admin.reports.attendanceDetail.table.purchasedAt"), width: 92 },
    { label: t("admin.reports.attendanceDetail.table.ticketStatus"), width: 62 },
    { label: t("admin.reports.attendanceDetail.table.orderStatus"), width: 62 },
    { label: t("admin.reports.attendanceDetail.table.entryUse"), width: 97 },
  ] as const;
  const headerRowHeight = 24;
  const ticketRowHeight = 48;

  const drawTableHeader = () => {
    doc.setFillColor(26, 31, 40);
    doc.rect(marginX, y, contentWidth, headerRowHeight, "F");
    doc.setTextColor(244, 246, 249);
    doc.setFont(PDF_FONT_FAMILY, "bold");
    doc.setFontSize(9);

    let cursorX = marginX + 10;
    columns.forEach((column) => {
      doc.text(fitText(doc, column.label, column.width - 8), cursorX, y + 15);
      cursorX += column.width;
    });
    y += headerRowHeight;
  };

  if (details.occupied_tickets.length === 0) {
    ensureSpace(48);
    doc.setTextColor(88, 96, 112);
    doc.setFont(PDF_FONT_FAMILY, "normal");
    doc.setFontSize(10);
    doc.text(t("admin.reports.attendanceDetail.buyers.emptyText"), marginX, y + 12);
    y += 24;
  } else {
    ensureSpace(headerRowHeight, drawTableHeader);
    drawTableHeader();

    details.occupied_tickets.forEach((ticket, index) => {
      ensureSpace(ticketRowHeight, drawTableHeader);
      doc.setFillColor(index % 2 === 0 ? 250 : 244, index % 2 === 0 ? 252 : 246, index % 2 === 0 ? 255 : 249);
      doc.setDrawColor(228, 232, 238);
      doc.rect(marginX, y, contentWidth, ticketRowHeight, "FD");
      const usageStyle = seatUsageStyles[getSeatUsageTone(ticket)];
      doc.setFillColor(usageStyle.border[0], usageStyle.border[1], usageStyle.border[2]);
      doc.rect(marginX, y, 4, ticketRowHeight, "F");
      doc.setTextColor(40, 46, 58);
      doc.setFont(PDF_FONT_FAMILY, "normal");
      doc.setFontSize(8.5);

      let cursorX = marginX + 10;
      const rowTop = y;
      const drawSingleLineCell = (value: string, columnIndex: number) => {
        const column = columns[columnIndex];
        doc.setTextColor(40, 46, 58);
        doc.setFont(PDF_FONT_FAMILY, "normal");
        doc.setFontSize(8.2);
        doc.text(fitText(doc, value, column.width - 12), cursorX, rowTop + 26);
        cursorX += column.width;
      };
      const drawTwoLineCell = (primary: string, secondary: string, columnIndex: number) => {
        const column = columns[columnIndex];
        doc.setTextColor(25, 31, 43);
        doc.setFont(PDF_FONT_FAMILY, "bold");
        doc.setFontSize(8.2);
        doc.text(fitText(doc, primary, column.width - 12), cursorX, rowTop + 16);
        doc.setTextColor(88, 96, 112);
        doc.setFont(PDF_FONT_FAMILY, "normal");
        doc.setFontSize(7.2);
        doc.text(fitText(doc, secondary, column.width - 12), cursorX, rowTop + 31);
        cursorX += column.width;
      };

      drawTwoLineCell(
        buildSeatKey(ticket.seat_row, ticket.seat_number),
        `${t("common.labels.row")} ${ticket.seat_row} / ${t("common.labels.seat")} ${ticket.seat_number}`,
        0,
      );

      doc.setTextColor(25, 31, 43);
      doc.setFont(PDF_FONT_FAMILY, "bold");
      doc.setFontSize(8.2);
      doc.text(
        fitText(
          doc,
          ticket.user_name || t("admin.reports.attendanceDetail.buyers.buyerFallback"),
          columns[1].width - 12,
        ),
        cursorX,
        rowTop + 14,
      );
      doc.setTextColor(88, 96, 112);
      doc.setFont(PDF_FONT_FAMILY, "normal");
      doc.setFontSize(7.2);
      doc.text(fitText(doc, ticket.user_email || "-", columns[1].width - 12), cursorX, rowTop + 28);
      cursorX += columns[1].width;

      drawTwoLineCell(
        formatPdfDate(ticket.purchased_at, language),
        `${formatTime(ticket.purchased_at, language)} | ${formatCurrency(ticket.price, language)}`,
        2,
      );
      drawSingleLineCell(formatStateLabel(ticket.status), 3);
      drawSingleLineCell(
        ticket.order_status ? formatStateLabel(ticket.order_status) : t("admin.reports.attendanceDetail.buyers.noOrderStatus"),
        4,
      );

      if (isTicketCancelled(ticket)) {
        doc.setTextColor(146, 50, 47);
      } else if (ticket.checked_in_at) {
        doc.setTextColor(164, 92, 38);
      } else {
        doc.setTextColor(46, 116, 78);
      }
      doc.setFont(PDF_FONT_FAMILY, "bold");
      doc.setFontSize(8.2);
      doc.text(fitText(doc, getTicketUsageLabel(ticket), columns[5].width - 12), cursorX, rowTop + 14);
      doc.setTextColor(88, 96, 112);
      doc.setFont(PDF_FONT_FAMILY, "normal");
      doc.setFontSize(7.2);
      doc.text(fitText(doc, getTicketUsageDetail(ticket), columns[5].width - 12), cursorX, rowTop + 28);
      y += ticketRowHeight;
    });
  }

  ensureSpace(32);
  doc.setTextColor(112, 118, 132);
  doc.setFont(PDF_FONT_FAMILY, "normal");
  doc.setFontSize(8);
  doc.text(
    fitText(
      doc,
      t("admin.reports.attendanceDetail.pdf.footerSummary", {
        date: reportDate,
        tickets: details.tickets_sold,
        used: checkedInTicketsCount,
        available: details.seat_map.available_seats,
      }),
      contentWidth,
    ),
    marginX,
    y + 16,
  );

  const pageCount = doc.getNumberOfPages();
  for (let pageNumber = 1; pageNumber <= pageCount; pageNumber += 1) {
    doc.setPage(pageNumber);
    doc.setDrawColor(224, 229, 236);
    doc.line(marginX, pageHeight - 30, pageWidth - marginX, pageHeight - 30);
    doc.setTextColor(112, 118, 132);
    doc.setFont(PDF_FONT_FAMILY, "normal");
    doc.setFontSize(8);
    doc.text(fitText(doc, movieTitle, contentWidth - 120), marginX, pageHeight - 16);
    doc.text(
      t("admin.reports.attendanceDetail.pdf.pageLabel", { page: pageNumber, total: pageCount }),
      pageWidth - marginX,
      pageHeight - 16,
      { align: "right" },
    );
  }

  const fileName = `${sanitizeFileSegment(t("admin.reports.attendanceDetail.pdf.fileNamePrefix")) || "attendance"}-${sanitizeFileSegment(movieTitle) || "session"}.pdf`;
  doc.save(fileName);
}
