const categories = JSON.parse(document.getElementById('categories-data')?.textContent || '[]');
const workshops = document.querySelectorAll(".workshop-card");
const filterButtons = document.querySelectorAll(".category-filter-btn");
const searchInput = document.getElementById("workshop-search-input");
const filterRegistedBtn = document.getElementById("registered-filter-btn");
const hideCancelledBtn = document.getElementById("cancelled-filter-btn");
const clearFiltersBtn = document.getElementById("clear-filters-btn");
const noResultsMessage = document.getElementById("no-results-message");
const workshopCountEl = document.getElementById("workshop-count");
const visibleCountEl = document.getElementById("visible-count");
const totalCountEl = document.getElementById("total-count");

const filterState = {
    categories: new Set(),
    searchTerm: "",
    showRegisteredOnly: false,
    hideCancelled: false
}

function toggleButton(button) {
    button.classList.toggle("active");
    button.classList.toggle("btn-dark");
    button.classList.toggle("btn-white");

    return button.classList.contains("active");
}

function isAnyFilterActive() {
    return filterState.categories.size > 0
        || filterState.searchTerm !== ""
        || filterState.showRegisteredOnly
        || filterState.hideCancelled;
}

function updateClearButton() {
    if (clearFiltersBtn) {
        clearFiltersBtn.classList.toggle("d-none", !isAnyFilterActive());
    }
}

function updateWorkshopCount(visibleCount) {
    if (!workshopCountEl) return;
    const total = workshops.length;
    if (totalCountEl) totalCountEl.textContent = total;
    if (visibleCountEl) visibleCountEl.textContent = visibleCount;
    workshopCountEl.classList.toggle("d-none", !isAnyFilterActive());
}

function filterWorkshops() {
    const searchTerm = searchInput.value.toLowerCase();
    let visibleCount = 0;

    workshops.forEach(workshop => {
        const title = workshop.querySelector(".workshop-title")?.textContent?.toLowerCase() || "";
        const description = workshop.querySelector(".workshop-short-description")?.textContent?.toLowerCase() || "";
        const status = workshop.getAttribute("data-status");

        const workshopCategories = workshop.getAttribute("data-categories").split(",");
        const isRegistered = workshop.getAttribute("data-registered") === "True";

        const matchesCategory = filterState.categories.size === 0 || workshopCategories.some(cat => filterState.categories.has(cat));
        const matchesRegistered = !filterState.showRegisteredOnly || isRegistered;
        const matchesSearch = searchTerm === "" || title.includes(searchTerm) || description.includes(searchTerm);
        const matchesCancelled = !filterState.hideCancelled || status !== "X";

        if (matchesCategory && matchesRegistered && matchesSearch && matchesCancelled) {
            workshop.classList.remove("workshop-hidden");
            visibleCount++;
        } else {
            workshop.classList.add("workshop-hidden");
        }
    });

    // Show/hide no results message
    if (noResultsMessage) {
        noResultsMessage.classList.toggle("d-none", visibleCount > 0);
    }

    updateWorkshopCount(visibleCount);
    updateClearButton();
}

function clearAllFilters() {
    // Reset state
    filterState.categories.clear();
    filterState.searchTerm = "";
    filterState.showRegisteredOnly = false;
    filterState.hideCancelled = false;

    // Reset search input
    if (searchInput) searchInput.value = "";

    // Reset category buttons
    filterButtons.forEach(button => {
        button.classList.remove("active", "btn-dark");
        button.classList.add("btn-white");
    });

    // Reset additional filter buttons
    [filterRegistedBtn, hideCancelledBtn].forEach(btn => {
        if (btn) {
            btn.classList.remove("active", "btn-dark");
            btn.classList.add("btn-white");
        }
    });

    filterWorkshops();
}

filterButtons?.forEach(button => {
    button.addEventListener("click", () => {
        const category = button.getAttribute("data-category");

        if (toggleButton(button)) {
            filterState.categories.add(category);
        } else {
            filterState.categories.delete(category);
        }

        filterWorkshops();
    });
});

filterRegistedBtn?.addEventListener("click", () => {
    filterState.showRegisteredOnly = toggleButton(filterRegistedBtn);
    filterWorkshops();
})

searchInput?.addEventListener("input", () => {
    filterState.searchTerm = searchInput.value.toLowerCase();
    filterWorkshops();
});

hideCancelledBtn?.addEventListener("click", () => {
    filterState.hideCancelled = toggleButton(hideCancelledBtn);
    filterWorkshops();
});

clearFiltersBtn?.addEventListener("click", clearAllFilters);
