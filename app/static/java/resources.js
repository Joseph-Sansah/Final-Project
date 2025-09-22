 document.addEventListener("DOMContentLoaded", function () {
    const searchInput = document.getElementById("search-resources");
    const filterSelect = document.getElementById("filter-category");
    const resourceCards = document.querySelectorAll(".resource-card");
    const noResults = document.getElementById("no-results");

    function filterResources() {
      const searchQuery = searchInput.value.toLowerCase().trim();
      const selectedCategory = filterSelect.value;

      let visibleCount = 0;

      resourceCards.forEach(card => {
        const title = card.dataset.title;
        const category = card.dataset.category;
        const matchesSearch = title.includes(searchQuery);
        const matchesCategory = selectedCategory === "all" || category === selectedCategory;

        if (matchesSearch && matchesCategory) {
          card.style.display = "block";
          visibleCount++;
        } else {
          card.style.display = "none";
        }
      });

      noResults.style.display = visibleCount === 0 ? "block" : "none";
    }

    searchInput.addEventListener("input", filterResources);
    filterSelect.addEventListener("change", filterResources);
  });



  let selectedResourceId = null;

  function showRatingModal(resourceId) {
    // Fetch resource title (you could also pass it as a param)
    const titleEl = document.querySelector(`[data-category][data-title] h3`);
    const title = titleEl ? titleEl.textContent : "this resource";

    document.getElementById("modal-resource-title").textContent = `How would you rate "${title}"?`;
    document.getElementById("modal-resource-id").value = resourceId;
    document.getElementById("rating-modal").style.display = "flex";
    document.getElementById("review-comment").value = "";
    // Clear previous stars
    document.querySelectorAll('.star-input input[type="radio"]').forEach(r => r.checked = false);
  }

  function hideRatingModal() {
    document.getElementById("rating-modal").style.display = "none";
  }

  async function submitRating() {
    const resourceId = document.getElementById("modal-resource-id").value;
    const ratingInput = document.querySelector('.star-input input[type="radio"]:checked');
    const rating = ratingInput ? ratingInput.value : null;
    const comment = document.getElementById("review-comment").value;

    if (!rating) {
      alert("Please select a star rating.");
      return;
    }

    const response = await fetch("{{ url_for('main.rate_resource') }}", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": "{{ csrf_token() }}"  /* Enable CSRF if using Flask-WTF */
      },
      body: JSON.stringify({
        resource_id: parseInt(resourceId),
        rating: parseInt(rating),
        comment: comment
      })
    });

    const result = await response.json();

    if (response.ok) {
      alert("Thank you for your rating!");
      location.reload();  // Refresh to show updated rating
    } else {
      alert("Error: " + result.message);
    }
  }

  // Close modal on click outside
  window.onclick = function(event) {
    const modal = document.getElementById("rating-modal");
    if (event.target === modal) {
      hideRatingModal();
    }
  };

