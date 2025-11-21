import React from "react";
import axios from "axios";

export default function FileUploader({ onUploadSuccess }) {
  const handleFile = async (e) => {
    const file = e.target.files[0];
    let formData = new FormData();
    formData.append("file", file);

    const response = await axios.post("http://127.0.0.1:8000/upload", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });

    alert("File uploaded!");
    onUploadSuccess(response.data.columns); // Pass column names to parent
  };

  return (
    <div>
      <h3>Upload CSV File:</h3>
      <input type="file" accept=".csv" onChange={handleFile} />
    </div>
  );
}
