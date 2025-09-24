// Main JavaScript for AI Assignment Checker

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form validation and progress tracking
    initializeUploadForm();
    initializeFilePreview();
    initializeDragAndDrop();
});

function initializeUploadForm() {
    const form = document.getElementById('uploadForm');
    const submitBtn = document.getElementById('submitBtn');
    const progressDiv = document.getElementById('uploadProgress');
    const progressBar = progressDiv ? progressDiv.querySelector('.progress-bar') : null;

    if (form) {
        form.addEventListener('submit', function(e) {
            // Validate files before submission
            if (!validateFiles()) {
                e.preventDefault();
                return false;
            }

            // Show progress and disable button
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            }

            if (progressDiv) {
                progressDiv.style.display = 'block';
                simulateProgress();
            }
        });
    }
}

function validateFiles() {
    const questionFile = document.getElementById('question_file');
    const answerFiles = document.getElementById('answer_files');
    
    let isValid = true;
    let errorMessage = '';

    // Validate question file
    if (!questionFile.files.length) {
        errorMessage += 'Please select a question paper file.\n';
        isValid = false;
    } else {
        if (!isValidFileType(questionFile.files[0])) {
            errorMessage += 'Question paper must be PDF, Image, or Text file.\n';
            isValid = false;
        }
        if (questionFile.files[0].size > 16 * 1024 * 1024) {
            errorMessage += 'Question paper file is too large (max 16MB).\n';
            isValid = false;
        }
    }

    // Validate answer files
    if (!answerFiles.files.length) {
        errorMessage += 'Please select at least one answer sheet.\n';
        isValid = false;
    } else {
        for (let file of answerFiles.files) {
            if (!isValidFileType(file)) {
                errorMessage += `Invalid file type for ${file.name}. Only PDF, Images, and Text files are allowed.\n`;
                isValid = false;
            }
            if (file.size > 16 * 1024 * 1024) {
                errorMessage += `File ${file.name} is too large (max 16MB).\n`;
                isValid = false;
            }
        }
    }

    if (!isValid) {
        alert(errorMessage);
    }

    return isValid;
}

function isValidFileType(file) {
    const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'text/plain'];
    return validTypes.includes(file.type) || file.name.toLowerCase().match(/\.(pdf|png|jpg|jpeg|gif|txt)$/);
}

function simulateProgress() {
    const progressBar = document.querySelector('#uploadProgress .progress-bar');
    if (!progressBar) return;

    let progress = 0;
    const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress > 90) progress = 90;
        
        progressBar.style.width = progress + '%';
        progressBar.setAttribute('aria-valuenow', progress);
        
        if (progress >= 90) {
            clearInterval(interval);
            progressBar.style.width = '100%';
        }
    }, 500);
}

function initializeFilePreview() {
    const questionFile = document.getElementById('question_file');
    const answerFiles = document.getElementById('answer_files');

    if (questionFile) {
        questionFile.addEventListener('change', function(e) {
            updateFilePreview('question', e.target.files);
        });
    }

    if (answerFiles) {
        answerFiles.addEventListener('change', function(e) {
            updateFilePreview('answers', e.target.files);
        });
    }
}

function updateFilePreview(type, files) {
    let previewId = type === 'question' ? 'questionPreview' : 'answersPreview';
    let existingPreview = document.getElementById(previewId);
    
    // Remove existing preview
    if (existingPreview) {
        existingPreview.remove();
    }

    if (files.length === 0) return;

    // Create preview container
    const previewDiv = document.createElement('div');
    previewDiv.id = previewId;
    previewDiv.className = 'mt-2 p-2 border rounded bg-light';

    let previewHTML = `<small class="text-muted"><strong>${type === 'question' ? 'Question Paper' : 'Answer Sheets'}:</strong></small><ul class="mb-0 mt-1">`;

    for (let file of files) {
        const fileSize = (file.size / 1024 / 1024).toFixed(2);
        const fileIcon = getFileIcon(file.name);
        previewHTML += `<li><i class="${fileIcon} me-1"></i>${file.name} (${fileSize} MB)</li>`;
    }

    previewHTML += '</ul>';
    previewDiv.innerHTML = previewHTML;

    // Insert preview after the appropriate file input
    const inputElement = type === 'question' ? 
        document.getElementById('question_file') : 
        document.getElementById('answer_files');
    
    inputElement.parentNode.insertBefore(previewDiv, inputElement.nextSibling);
}

function getFileIcon(filename) {
    const extension = filename.toLowerCase().split('.').pop();
    const icons = {
        'pdf': 'fas fa-file-pdf text-danger',
        'png': 'fas fa-file-image text-primary',
        'jpg': 'fas fa-file-image text-primary',
        'jpeg': 'fas fa-file-image text-primary',
        'gif': 'fas fa-file-image text-primary',
        'txt': 'fas fa-file-alt text-secondary'
    };
    return icons[extension] || 'fas fa-file text-muted';
}

function initializeDragAndDrop() {
    const fileInputs = document.querySelectorAll('input[type="file"]');
    
    fileInputs.forEach(input => {
        const container = input.closest('.mb-4') || input.parentElement;
        
        // Add drag and drop styling
        container.addEventListener('dragover', function(e) {
            e.preventDefault();
            container.classList.add('dragover');
        });

        container.addEventListener('dragleave', function(e) {
            e.preventDefault();
            container.classList.remove('dragover');
        });

        container.addEventListener('drop', function(e) {
            e.preventDefault();
            container.classList.remove('dragover');
            
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                input.files = files;
                // Trigger change event
                const event = new Event('change', { bubbles: true });
                input.dispatchEvent(event);
            }
        });
    });
}

// Utility function to show notifications
function showNotification(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible fade show position-fixed`;
    alertDiv.style.cssText = 'top: 20px; right: 20px; z-index: 1050; min-width: 300px;';
    
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(alertDiv);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

// Add smooth scrolling to anchors
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
        e.preventDefault();
        const target = document.querySelector(this.getAttribute('href'));
        if (target) {
            target.scrollIntoView({
                behavior: 'smooth'
            });
        }
    });
});

// Initialize tooltips if Bootstrap is available
if (typeof bootstrap !== 'undefined') {
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Add fade-in animation to cards
document.querySelectorAll('.card').forEach((card, index) => {
    card.style.animationDelay = `${index * 0.1}s`;
    card.classList.add('fade-in');
});