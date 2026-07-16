// Thư viện lừa đảo — module riêng cho trang /library.html.
// Tách khỏi app.js để trang kiểm tra (/) không còn fetch /api/scam-library
// và không phụ thuộc DOM của thư viện. Mọi render dùng textContent/DOM API.
// Thiết lập chỉ chạy khi các node thư viện tồn tại; không ném nếu thiếu.

import { ApiError, getScamLibrary } from "./api.js";
import { filterLibraryItems, libraryGroupFromHash } from "./stage3-model.js?v=stage5-tabs-v6";
import { wirePreferences } from "./preferences.js";

function createElement(tag, { className = "", text = "", attributes = {} } = {}) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  Object.entries(attributes).forEach(([name, value]) => element.setAttribute(name, value));
  return element;
}

function renderLibrary(scope, data, group = "all", query = "") {
  const groups = data.groups.map((item) => item.key);
  const activeGroup = groups.includes(group) ? group : "all";
  scope.filters.replaceChildren();
  [{ key: "all", label: "Tất cả" }, ...data.groups].forEach((filter) => {
    scope.filters.append(createElement("button", {
      className: "library-filter",
      text: filter.label,
      attributes: {
        type: "button",
        "data-library-group": filter.key,
        "aria-pressed": String(filter.key === activeGroup),
      },
    }));
  });

  const items = filterLibraryItems(data.items, activeGroup, query, data.groups);
  scope.list.replaceChildren();
  if (!items.length) {
    const empty = createElement("div", { className: "library-empty" });
    empty.append(
      createElement("h2", { text: "Chưa có mẫu trong nhóm này" }),
      createElement("p", { text: "Bác thử xoá từ khoá, chọn “Tất cả” hoặc một nhóm khác." }),
    );
    scope.list.append(empty);
  }
  items.forEach((item) => {
    const article = createElement("details", {
      className: "library-item",
      attributes: { id: item.slug, "data-library-item": item.id },
    });
    const summary = createElement("summary", { className: "library-item-summary" });
    const summaryCopy = createElement("span");
    summaryCopy.append(
      createElement("span", {
        className: "library-group-label",
        text: data.groups.find((groupItem) => groupItem.key === item.group)?.label || "",
      }),
      createElement("span", { className: "library-item-title", text: item.title }),
    );
    summary.append(
      summaryCopy,
      createElement("span", {
        className: "library-toggle-label",
        text: "Xem dấu hiệu",
        attributes: { "aria-hidden": "true" },
      }),
    );
    const content = createElement("div", { className: "library-item-content" });
    content.append(createElement("p", { text: item.summary }));
    const signs = createElement("ul", { className: "library-signs" });
    item.warning_signs.forEach((sign) => signs.append(createElement("li", { text: sign })));
    content.append(
      signs,
      createElement("p", { className: "library-safe-action", text: `Nên làm: ${item.safe_action}` }),
    );
    article.append(summary, content);
    scope.list.append(article);
  });
  if (scope.status) scope.status.textContent = `Đang hiển thị ${items.length} kiểu lừa đảo.`;
}

/**
 * Khởi tạo thư viện. Trả về true nếu đã lắp được (tìm thấy node list/filters),
 * false nếu trang không có thư viện — gọi an toàn từ bất kỳ trang nào.
 */
export function setupLibrary() {
  const list = document.getElementById("libraryList");
  const filters = document.getElementById("libraryFilters");
  if (!list || !filters) return false;

  const status = document.getElementById("libraryStatus");
  const errorBox = document.getElementById("libraryError");
  const search = document.getElementById("librarySearch");
  const scope = { list, filters, status, errorBox, search };
  let data = { groups: [], items: [] };

  filters.addEventListener("click", (event) => {
    const button = event.target.closest("[data-library-group]");
    if (!button) return;
    const group = button.dataset.libraryGroup;
    if (group === "all") {
      history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    } else {
      window.location.hash = group;
    }
    renderLibrary(scope, data, group, search?.value || "");
  });

  if (search) {
    search.addEventListener("input", () => {
      renderLibrary(scope, data, libraryGroupFromHash(
        window.location.hash,
        data.groups.map((item) => item.key),
      ), search.value);
    });
  }

  window.addEventListener("hashchange", () => {
    renderLibrary(scope, data, libraryGroupFromHash(
      window.location.hash,
      data.groups.map((item) => item.key),
    ), search?.value || "");
  });

  const load = async () => {
    if (status) status.textContent = "Đang tải thư viện…";
    if (errorBox) {
      errorBox.hidden = true;
      errorBox.replaceChildren();
    }
    list.setAttribute("aria-busy", "true");
    try {
      data = await getScamLibrary();
      renderLibrary(scope, data, libraryGroupFromHash(
        window.location.hash,
        data.groups.map((item) => item.key),
      ), search?.value || "");
      list.removeAttribute("aria-busy");
    } catch (error) {
      if (status) status.textContent = "";
      if (errorBox) {
        const retry = createElement("button", {
          className: "button-secondary library-retry",
          text: "Thử tải lại thư viện",
          attributes: { type: "button" },
        });
        retry.addEventListener("click", load);
        errorBox.replaceChildren(
          createElement("p", {
            text: error instanceof ApiError
              ? error.message
              : "Chưa tải được thư viện. Bác vui lòng thử lại sau.",
          }),
          retry,
        );
        errorBox.hidden = false;
      }
      list.removeAttribute("aria-busy");
    }
  };

  load();
  return true;
}

setupLibrary();

const displayPrefs = document.getElementById("displayPrefs");
if (displayPrefs) wirePreferences({ root: displayPrefs });
