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
    "Ctrl-Space": "autocomplete"
  }
});


var purlYamlHint = function(editor, options) {
  /* Generates completion hints depending on the current cursor position of the yaml file */
  var cursor = editor.getCursor();
  var thisLine = editor.getLine(cursor.line);
  var currEnd = cursor.ch;
  var currStart = currEnd;

  // Look left and right from the current cursor position to have in view the entire word at that
  // location:
  while (currStart && /[\w$]+/.test(thisLine.charAt(currStart - 1))) {
    --currStart;
  }
  while (currEnd && /[\w$]+/.test(thisLine.charAt(currEnd))) {
    ++currEnd;
  }
  var currWord = thisLine.slice(currStart, currEnd);

  var currContext = function() {
    /* Finds the nearest root-level directive above the current line (if one exists) and returns its
       name. */
    var lineNum = cursor.line;
    var matches = /^(\w+):/.exec(editor.getLine(lineNum));
    while (!matches && lineNum > 0) {
      matches = /^(\w+):/.exec(editor.getLine(--lineNum));
    }
    return matches && matches[1];
  };

  // The beginning and ending positions of the text that will be replaced if a completion
  // hint is selected:
  var from = CodeMirror.Pos(cursor.line, currStart);
  var to = CodeMirror.Pos(cursor.line, currEnd);

  // If there is no word here just return an empty list:
  if (currStart === currEnd) {
    return {list: [], from: from, to: to}
  }

  var pruneReplacementList = function(replacementList) {
    /* Prunes the given list of completions to only those which begin with the current word.
       If none match, then returns the entire list.
       If there is only one match and it is exact, return nothing.  */
    prunedList = replacementList.filter(function(r) {
      return (new RegExp("^" + currWord).test(r['displayText']));
    });
    if (!prunedList || prunedList.length === 0) {
      return replacementList;
    }
    else if (prunedList.length === 1 && prunedList[0]['displayText'] === currWord) {
      return [];
    }
    else {
      return prunedList;
    }
  };

  // Send back a completion hint lists contextualised to the current current position as well as to
  // the letters that have been typed so far.
  var prevString = thisLine.slice(0, currStart);
  if (prevString === '') {
    return {list: pruneReplacementList([{displayText: 'base_redirect: ', text: 'base_redirect: '},
                                        {displayText: 'base_url:', text: 'base_url: '},
                                        {displayText: 'entries:', text: 'entries:\n- '},
                                        {displayText: 'example_terms:', text: 'example_terms:\n- '},
                                        {displayText: 'idspace:', text: 'idspace: '},
                                        {displayText: 'products:', text: 'products:\n- '},
                                        {displayText: 'term_browser:', text: 'term_browser: '},
                                        {displayText: 'tests:', text: 'tests:\n- from: \n  to: '}]),
            from: from, to: to};
  }
  else if (/^term_browser:\s+$/.test(prevString)) {
    return {list: pruneReplacementList([{displayText: 'ontobee', text: 'ontobee'},
                                        {displayText: 'custom', text: 'custom'}]),
            from: from, to: to};
  }
  else if (/^base_url:\s+$/.test(prevString)) {
    return {list: pruneReplacementList([{displayText: '/obo/', text: '/obo/'}]),
            from: from, to: to};
  }
  else if (/^-\s+$/.test(prevString) && currContext() === 'tests') {
    return {list: pruneReplacementList([{displayText: 'from:', text: 'from: \n  to: '},
                                        {displayText: 'to:', text: 'to: '}]),
            from: from, to: to};
  }
  else if (/^-\s+$/.test(prevString) && currContext() === 'entries') {
    return {list: pruneReplacementList([{displayText: 'exact:', text: 'exact: \n  replacement: '},
                                        {displayText: 'prefix:', text: 'prefix: \n  replacement: '},
                                        {displayText: 'regex:', text: 'regex: \n  replacement: '}]),
            from: from, to: to};
  }
  else if (prevString === '  ' && currContext() === 'entries') {
    return {list: pruneReplacementList([{displayText: 'replacement:', text: 'replacement: '},
                                        {displayText: 'status:', text: 'status: '},
                                        {displayText: 'tests:', text: 'tests:\n  - from: \n    to: '}]),
            from: from, to: to};
  }
};


// Add our custom hinting function to the editor:
CodeMirror.commands.autocomplete = function(cm) {
  cm.showHint({hint: purlYamlHint, completeSingle: false});
}


// Activate hint popup on any letter key press
editor.on("keyup", function (cm, event) {
  // If the autocompletion popup is not already active, and if the user has typed a letter,
  // then activate the autocompletion popup:
  if (!cm.state.completionActive) {
    // Letter keys only:
    keyPressed = event.key.toLowerCase();
    if (keyPressed >= 'a' && keyPressed <= 'z') {
      CodeMirror.commands.autocomplete(cm);
    }
  }
});


// Disable the save button when the contents of the editor are changed:
editor.on("change", function() {
  document.getElementById("save-btn").disabled = true;
});


// Disable the editor if the user refreshes or otherwise leaves the page:
window.onbeforeunload = function() {
  document.getElementById("save-btn").disabled = true;
}


var validate = function() {
  // Save the contents of the editor to its associated text area:
  editor.save();

  // Extract the code from the text area:
  var code = document.getElementById("code").value;

  // Clear the status area:
  var statusArea = document.getElementById("status-area");
  statusArea.style.color = "#000000";
  statusArea.innerHTML = "Validating ...";

  // Embed the code into a POST request and send it to the server for processing.
  // If the validation is successful, enable the Save button, otherwise disable it.
  var request = new XMLHttpRequest();
  request.onreadystatechange = function() {
    if (request.readyState === 4) {
      if (!request.status) {
        statusArea.style.color = "#FF0000";
        statusArea.innerHTML = "Problem communicating with server";
        document.getElementById("save-btn").disabled = true;
      }
      else if (request.status === 200) {
        statusArea.style.color = "#00CD00";
        statusArea.innerHTML = "Validation successful";
        document.getElementById("save-btn").disabled = false;
      }
      else {
        // Display the error message in the status area. Note that we must replace any angle
        // angle brackets with HTML escape codes.
        alertText = "Validation failed.\n\n" +
          request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
        alertText = '<div class="preformatted">' + alertText + '</div>';
        statusArea.style.color = "#FF0000";
        statusArea.innerHTML = alertText;
        document.getElementById("save-btn").disabled = true;
      }
    }
  }
  request.open('POST', 'http://127.0.0.1:5000/validate', true);
  request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  request.send("code=" + encodeURIComponent(code));
};


var save = function() {
  // Get a confirmation from the user:
  bootbox.confirm({ 
    size: "large",
    closeButton: false,
    title: "Confirm save",
    message: 'By saving now <b>you will initiate a pull request</b> in the purl.obolibrary.org ' +
      'repository containing the changes you have made to this file. Please confirm that you ' +
      'really want to do this.',
    buttons: {
      confirm: {
        label: 'Save',
        className: 'btn-danger'
      },
      cancel: {
        label: 'Cancel',
        className: 'btn-primary'
      }
    },
    callback: function(result) {
      if (result) {
        // Disable the save button:
        document.getElementById("save-btn").disabled = true;

        // Extract the code from the text area:
        var code = document.getElementById("code").value;

        // Clear the status area:
        var statusArea = document.getElementById("status-area");
        statusArea.style.color = "#000000";
        statusArea.innerHTML = "Saving ...";

        // Embed the code into a POST request and send it to the server for processing.
        var request = new XMLHttpRequest();
        request.onreadystatechange = function() {
          if (request.readyState === 4) {
            if (!request.status) {
              statusArea.style.color = "#FF0000";
              statusArea.innerHTML = "Problem communicating with server";
            }
            else if (request.status === 200) {
              statusArea.style.color = "#00CD00";
              statusArea.innerHTML = "Save successful";
            }
            else {
              // Display the error message in the status area. Note that we must replace any angle
              // angle brackets with HTML escape codes.
              alertText = "Save failed.\n\n" +
                request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
              alertText = '<div class="preformatted">' + alertText + '</div>';
              statusArea.style.color = "#FF0000";
              statusArea.innerHTML = alertText;
            }
          }
        }
        request.open('POST', 'http://127.0.0.1:5000/save', true);
        request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
        // TODO: agro.yml is hard-coded ...
        request.send("filename=" + 'agro.yml' + '&code=' + encodeURIComponent(code))
      }
    }
  });
};
