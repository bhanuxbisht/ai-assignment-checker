// Main JavaScript for AI Assignment Checker

// Global file storage for dynamic file management
let answerFiles = [];
let fileIdCounter = 0;

document.addEventListener('DOMContentLoaded', function() {
    // Initialize form validation and progress tracking
    initializeUploadForm();
    initializeFilePreview();
    initializeDragAndDrop();
    initializeDynamicFileManager();
});

function initializeDynamicFileManager() {
    const addFileBtn = document.getElementById('addFileBtn');
    const hiddenFileInput = document.getElementById('hiddenFileInput');
    
    if (addFileBtn && hiddenFileInput) {
        // When "Add File" button is clicked
        addFileBtn.addEventListener('click', function() {
            hiddenFileInput.click();
        });
        
        // When file is selected through hidden input
        hiddenFileInput.addEventListener('change', function(e) {
            const files = e.target.files;
            if (files.length > 0) {
                addFilesToList(files);
                // Reset the input so the same file can be added again if needed
                hiddenFileInput.value = '';
            }
        });
    }
}

function addFilesToList(files) {
    const filesList = document.getElementById('answerFilesList');
    
    Array.from(files).forEach(file => {
        // Check if file is valid
        if (!isValidFileType(file)) {
            showNotification(`Invalid file type for ${file.name}. Only PDF, Images, and Text files are allowed.`, 'warning');
            return;
        }
        
        if (file.size > 16 * 1024 * 1024) {
            showNotification(`File ${file.name} is too large (max 16MB).`, 'warning');
            return;
        }
        
        // Add file to global storage
        const fileId = fileIdCounter++;
        answerFiles.push({ id: fileId, file: file });
        
        // Create file card
        const fileCard = createFileCard(fileId, file);
        filesList.appendChild(fileCard);
    });
    
    updateFileCount();
}

function createFileCard(fileId, file) {
    const card = document.createElement('div');
    card.className = 'card mb-2 file-item';
    card.setAttribute('data-file-id', fileId);
    
    const fileSize = (file.size / 1024 / 1024).toFixed(2);
    const fileIcon = getFileIcon(file.name);
    
    card.innerHTML = `
        <div class="card-body p-2 d-flex align-items-center justify-content-between">
            <div class="d-flex align-items-center">
                <i class="${fileIcon} me-2 fa-lg"></i>
                <div>
                    <strong>${file.name}</strong>
                    <small class="text-muted d-block">${fileSize} MB</small>
                </div>
            </div>
            <button type="button" class="btn btn-sm btn-outline-danger remove-file-btn" 
                    data-file-id="${fileId}" title="Remove this file">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    // Add remove functionality
    const removeBtn = card.querySelector('.remove-file-btn');
    removeBtn.addEventListener('click', function() {
        removeFile(fileId);
    });
    
    return card;
}

function removeFile(fileId) {
    // Remove from global storage
    answerFiles = answerFiles.filter(f => f.id !== fileId);
    
    // Remove from DOM
    const fileCard = document.querySelector(`[data-file-id="${fileId}"]`);
    if (fileCard) {
        fileCard.remove();
    }
    
    updateFileCount();
    showNotification('File removed successfully', 'info');
}

function updateFileCount() {
    const addFileBtn = document.getElementById('addFileBtn');
    if (addFileBtn) {
        const count = answerFiles.length;
        addFileBtn.innerHTML = `
            <i class="fas fa-plus me-2"></i>
            Add Answer File ${count > 0 ? `(${count} added)` : ''}
        `;
    }
}

function initializeUploadForm() {
    const form = document.getElementById('uploadForm');
    const submitBtn = document.getElementById('submitBtn');
    const progressDiv = document.getElementById('uploadProgress');
    const progressBar = progressDiv ? progressDiv.querySelector('.progress-bar') : null;

    if (form) {
        form.addEventListener('submit', function(e) {
            e.preventDefault(); // Always prevent default to handle files manually
            
            // Validate files before submission
            if (!validateFiles()) {
                return false;
            }
            
            // Prepare FormData with dynamic files
            const formData = new FormData();
            
            // Add question file
            const questionFile = document.getElementById('question_file');
            if (questionFile.files.length > 0) {
                formData.append('question_file', questionFile.files[0]);
            }
            
            // Add answer files from global storage
            answerFiles.forEach(fileObj => {
                formData.append('answer_files', fileObj.file);
            });

            // Show progress and disable button
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i>Processing...';
            }

            if (progressDiv) {
                progressDiv.style.display = 'block';
                simulateProgress();
            }
            
            // Submit form via AJAX
            fetch(form.action, {
                method: 'POST',
                body: formData
            })
            .then(response => {
                if (response.ok) {
                    return response.text();
                }
                throw new Error('Upload failed');
            })
            .then(html => {
                // Replace page content with response
                document.open();
                document.write(html);
                document.close();
            })
            .catch(error => {
                console.error('Error:', error);
                showNotification('Upload failed. Please try again.', 'danger');
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = '<i class="fas fa-magic me-2"></i>Start AI Evaluation';
                }
                if (progressDiv) {
                    progressDiv.style.display = 'none';
                }
            });
        });
    }
}

function validateFiles() {
    const questionFile = document.getElementById('question_file');
    
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

    // Validate answer files from global storage
    if (answerFiles.length === 0) {
        errorMessage += 'Please add at least one answer sheet using "Add Answer File" button.\n';
        isValid = false;
    }

    if (!isValid) {
        showNotification(errorMessage, 'danger');
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

    if (questionFile) {
        questionFile.addEventListener('change', function(e) {
            updateFilePreview('question', e.target.files);
        });
    }
    
    // Note: Answer files preview is now handled by createFileCard() function
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