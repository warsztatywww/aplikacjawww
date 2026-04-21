const categories = JSON.parse(document.getElementById('categories-data')?.textContent || '[]');
const workshops = document.querySelectorAll(".workshop-card");
const filterButtons = document.querySelectorAll(".category-filter-btn");
const searchInput = document.getElementById("workshop-search-input");
const filterRegistedBtn = document.getElementById("registered-filter-btn");
const hideCancelledBtn = document.getElementById("cancelled-filter-btn");

const workshopTypeTabs = document.querySelectorAll(".workshop-type-tab");
const activeWorkshopType = document.querySelector(".workshop-type-tab.active")?.getAttribute("data-type") || null; 
const workshopTypeDescriptions = document.querySelectorAll(".workshop-type-description");

const filterState = {
    workshopType: activeWorkshopType,
    categories: new Set(),
    searchTerm: "",
    showRegisteredOnly: false,
    hideCancelled: false
}

function toggleButton(button) {
    button.classList.toggle("active");
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

        const matchesType = !filterState.workshopType || workshop.getAttribute("data-workshop-type") === filterState.workshopType;
        const matchesCategory = filterState.categories.size === 0 || workshopCategories.some(cat => filterState.categories.has(cat));
        const matchesRegistered = !filterState.showRegisteredOnly || isRegistered;
        const matchesSearch = searchTerm === "" || title.includes(searchTerm) || description.includes(searchTerm);
        const matchesCancelled = !filterState.hideCancelled || status !== "X";

        if (matchesType && matchesCategory && matchesRegistered && matchesSearch && matchesCancelled) {
            workshop.classList.remove("d-none");
        } else {
            workshop.classList.add("d-none");
        }
    });
}

workshopTypeTabs?.forEach(tab => {
    tab.addEventListener("click", () => {
        const selectedType = tab.getAttribute("data-type");

        if (filterState.workshopType !== selectedType) {
            filterState.workshopType = selectedType;
            workshopTypeTabs.forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
        }

        workshopTypeDescriptions.forEach(desc => {
            if (desc.getAttribute("data-type") === selectedType) {
                desc.classList.remove("d-none");
            } else {
                desc.classList.add("d-none");
            }
        });

        filterWorkshops();
    })
});

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
