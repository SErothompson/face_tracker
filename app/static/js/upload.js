/**
 * Photo upload preview and validation script
 */

document.addEventListener('DOMContentLoaded', function() {
    const photoInputs = document.querySelectorAll('.photo-input');
    const optionalPhotoInputs = document.querySelectorAll('.photo-input-optional');
    const submitBtn = document.getElementById('submitBtn');
    const requiredAngles = ['front', 'left', 'right'];

    // Set up event listeners for required photos
    photoInputs.forEach(input => {
        input.addEventListener('change', function() {
            const angle = this.name.replace('photo_', '');
            handlePhotoSelected(this, angle);
            checkAllRequiredPhotosSelected();
        });
    });

    // Set up event listeners for optional photos
    optionalPhotoInputs.forEach(input => {
        input.addEventListener('change', function() {
            const angle = this.name.replace('photo_', '');
            handlePhotoSelected(this, angle);
        });
    });

    function handlePhotoSelected(input, angle) {
        const file = input.files[0];
        const previewDiv = document.getElementById(`preview_${angle}`);
        const placeholderDiv = document.getElementById(`placeholder_${angle}`);
        const imgElement = document.getElementById(`img_${angle}`);

        if (file) {
            // Validate file type
            const allowedTypes = ['image/png', 'image/jpeg', 'image/webp'];
            if (!allowedTypes.includes(file.type)) {
                alert(`Invalid file type for ${angle} photo. Please use PNG, JPG, or WebP.`);
                input.value = '';
                placeholderDiv.style.display = 'flex';
                previewDiv.style.display = 'none';
                return;
            }

            // Validate file size (max 16MB)
            const maxSize = 16 * 1024 * 1024;
            if (file.size > maxSize) {
                alert(`File too large. Maximum 16 MB. Your file: ${(file.size / (1024 * 1024)).toFixed(2)} MB`);
                input.value = '';
                placeholderDiv.style.display = 'flex';
                previewDiv.style.display = 'none';
                return;
            }

            // Read and display preview
            const reader = new FileReader();
            reader.onload = function(e) {
                imgElement.src = e.target.result;
                previewDiv.style.display = 'block';
                placeholderDiv.style.display = 'none';
            };
            reader.readAsDataURL(file);
        } else {
            // No file selected
            previewDiv.style.display = 'none';
            placeholderDiv.style.display = 'flex';
        }
    }

    function checkAllRequiredPhotosSelected() {
        const allSelected = requiredAngles.every(angle => {
            const input = document.querySelector(`input[name="photo_${angle}"]`);
            return input && input.files.length > 0;
        });

        submitBtn.disabled = !allSelected;
    }

    // Prevent form submission if validation fails
    const form = document.getElementById('uploadForm');
    form.addEventListener('submit', function(e) {
        const allSelected = requiredAngles.every(angle => {
            const input = document.querySelector(`input[name="photo_${angle}"]`);
            return input && input.files.length > 0;
        });

        if (!allSelected) {
            e.preventDefault();
            alert('Please select all three required photos (front, left, right) before uploading.');
        }
    });
});

