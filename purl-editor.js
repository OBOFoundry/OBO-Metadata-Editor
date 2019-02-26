var validate = function() {
  // Save the contents of the editor to its associated text area:
  editor.save();

  // Extract the code from the text area:
  var code = document.getElementById("code").value;

  // Embed it into a POST request and send it to the server for processing:
  var request = new XMLHttpRequest();
  request.onreadystatechange = function() { //Call a function when the state changes.
    if(request.readyState == 4) {
      // Request finished. Do processing here.
      console.log("Status: " + request.status + ", Text: " + request.responseText);
    }
  }
  request.open('POST', 'http://127.0.0.1:5000/validate', true);
  request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  request.send("code=" + encodeURIComponent(code));
};

var editor = CodeMirror.fromTextArea(document.getElementById("code"), {
  mode: "text/x-yaml",
  theme: "default",
  lineNumbers: true,
  matchBrackets: true,
  showCursorWhenSelecting: true,
  extraKeys: {
    "F11": function(cm) {
      if (!cm.getOption("fullScreen")) {
        bootbox.dialog({
          title: 'Entering fullscreen editor mode',
          message: 'To leave fullscreen mode, press F11 or Esc',
          closeButton: false,
          buttons: {
            ok: {
              label: 'Ok',
            },
          },
        });
      }
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
    "Ctrl-S": validate,
  }
});
