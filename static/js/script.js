
function confirmDelete() {
    return confirm(
        "Are you sure you want to delete this story? This action cannot be undone."
    );
}

// Automatically hide flash messages
document.addEventListener("DOMContentLoaded", function () {
    const messages = document.querySelectorAll(".flash");

    messages.forEach(function (message) {
        setTimeout(function () {
            message.style.transition = "opacity 0.5s ease";
            message.style.opacity = "0";

            setTimeout(function () {
                message.remove();
            }, 500);

        }, 3500);
    });
});
