var validateAndSave = function() {
    // VALIDATION SHOULD BE DONE FIRST
    editor.save();
    var code = document.getElementById("code").value;
    var filename = "Untitled.yml";
    var download_link = document.createElement("a");
    download_link.download = filename;

    // dummy name for the hidden link:
    download_link.innerHTML = "LINKTITLE";

    window.URL = window.URL || window.webkitURL;

    var code_blob = new Blob([code], {type:'text/plain'});
    download_link.href = window.URL.createObjectURL(code_blob);

    download_link.onclick = destroyClickedElement;
    download_link.style.display = "none";
    document.body.appendChild(download_link);
    download_link.click();
};

function destroyClickedElement(event) {
    document.body.removeChild(event.target);
}

var editor = CodeMirror.fromTextArea(document.getElementById("code"), {
    mode: "text/x-yaml",
    theme: "default",
    lineNumbers: true,
    matchBrackets: true,
    showCursorWhenSelecting: true,
    extraKeys: {
        "F11": function(cm) {
            if (!cm.getOption("fullScreen"))
                alert("To leave fullscreen mode, press F11 or Esc");
            cm.setOption("fullScreen", !cm.getOption("fullScreen"));
        },
        "Esc": function(cm) {
            if (cm.getOption("fullScreen"))
                cm.setOption("fullScreen", false);
        },
        Tab: function(cm) {
            var spaces = Array(cm.getOption("indentUnit") + 1).join(" ");
            cm.replaceSelection(spaces);
        },
        "Ctrl-S": validateAndSave,
    }
});
