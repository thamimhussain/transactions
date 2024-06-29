const btn = document.querySelector('#submitbtn')

btn.addEventListener("click", () => {

    var fileInput = document.getElementById('file');
    var bankSelect = document.getElementById('bank');

    if (fileInput.files.length === 0) {
        alert('Please select a file to upload.');
        return;
    }

    var formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('bank', bankSelect.value);

    fetch('/upload', {
        method: 'POST',
        body: formData
    });
})