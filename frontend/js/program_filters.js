const categories = JSON.parse(document.getElementById('categories-data')?.textContent || '[]');
const workshops = document.querySelectorAll(".workshop-card");
const filterButtons = document.querySelectorAll(".category-filter-btn");
const searchInput = document.getElementById("workshop-search-input");
const filterRegistedBtn = document.getElementById("registered-filter-btn");
const hideCancelledBtn = document.getElementById("cancelled-filter-btn");

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

function filterWorkshops() {
    const searchTerm = searchInput.value.toLowerCase();
        
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
            workshop.style.display = "block";
        } else {
            workshop.style.display = "none";
        }
    });
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
