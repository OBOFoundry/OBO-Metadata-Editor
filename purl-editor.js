var editor = CodeMirror.fromTextArea(document.getElementById("code"), {
  mode: "text/x-yaml",
  theme: "default",
  lineNumbers: true,
  matchBrackets: true,
  showCursorWhenSelecting: true,
  extraKeys: {
    "F11": function(cm) {
      if (!cm.getOption("fullScreen")) {
        bootbox.alert({
          title: 'Entering fullscreen editor mode',
          message: 'To leave fullscreen mode, press F11 or Esc',
          closeButton: false,
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

var validate = function() {
  // Save the contents of the editor to its associated text area:
  editor.save();

  // Extract the code from the text area:
  var code = document.getElementById("code").value;

  // Clear the validation area:
  var validationArea = document.getElementById("validation-area");
  validationArea.style.color = "#000000";
  validationArea.innerHTML = "Validating ...";

  // Embed the code into a POST request and send it to the server for processing:
  var request = new XMLHttpRequest();
  request.onreadystatechange = function() { //Call a function when the state changes.
    if (request.readyState === 4) {
      if (request.status === 200) {
        validationArea.style.color = "#00CD00";
        validationArea.innerHTML = "Validation successful";
        // TODO: Enable the Save button here
      }
      else {
        // Display the error message in the validation area. Note that we must replace any angle
        // angle brackets with HTML escape codes.
        alertText = "Validation failed.\n\n" +
          request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        alertText = '<div class="preformatted">' + alertText + '</div>';
        validationArea.style.color = "#FF0000";
        validationArea.innerHTML = alertText;
      }
    }
  }
  request.open('POST', 'http://127.0.0.1:5000/validate', true);
  request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  request.send("code=" + encodeURIComponent(code));
};
