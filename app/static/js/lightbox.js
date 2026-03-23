let lightboxImages = [];
let currentIndex = 0;

function openLightbox(startIndex, images) {
    lightboxImages = images;
    currentIndex = startIndex;

    const modal = new bootstrap.Modal(document.getElementById("lightboxModal"));
    const imgElement = document.getElementById("lightboxImage");

    imgElement.src = lightboxImages[currentIndex];
    modal.show();

    updateArrows();
}

function updateArrows() {
    document.getElementById("lightboxPrev").style.display =
        (currentIndex > 0) ? "block" : "none";

    document.getElementById("lightboxNext").style.display =
        (currentIndex < lightboxImages.length - 1) ? "block" : "none";
}

document.getElementById("lightboxPrev").addEventListener("click", () => {
    if (currentIndex > 0) {
        currentIndex--;
        document.getElementById("lightboxImage").src = lightboxImages[currentIndex];
        updateArrows();
    }
});

document.getElementById("lightboxNext").addEventListener("click", () => {
    if (currentIndex < lightboxImages.length - 1) {
        currentIndex++;
        document.getElementById("lightboxImage").src = lightboxImages[currentIndex];
        updateArrows();
    }
});
