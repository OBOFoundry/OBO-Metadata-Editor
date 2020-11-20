/**
 * Gets the document element corresponding to the "commit" button. This will be variable depending
 * on whether the editor is being used to update an existing or add a new config file.
 */
var get_commit_btn = function() {
  if (document.getElementById("update-btn")) {
    return document.getElementById("update-btn");
  }
  else {
    return document.getElementById("add-btn");
  }
}


/**
 * Enables and disables the "submit as draft" feature if validations fail
 */
let draft = false;
var set_draft = function(draft_val) {
    draft = draft_val;
    var btn_label = get_commit_btn().innerHTML.replace('as draft','');
    if (draft_val) {
        get_commit_btn().innerHTML = btn_label+ " as draft";
    } else {
        get_commit_btn().innerHTML = btn_label;
    }
}

/**
 * Shows or hides an element of text when a link is clicked
 */
function showHideText(elemToShow, elemToHide) {
    // show this element
    document.getElementById(elemToShow).style.display = 'inherit';
    // hide this element
    document.getElementById(elemToHide).style.display = 'none';
}

/**
 * Formats a String message as a dismissable Bootstrap alert text.
 * For example, passing parameter style = alert-danger gives a red box.
 */
function showAlertFor(text, style, extraText='') {
    $("#status-area").removeClass()
    $("#status-area").show()
    $("#status-area").addClass("alert "+style+" alert-dismissable fade show");
    $("#alert-message").html(text);

    if ( extraText.length > 0) {
        $("#details-area").show();
        $("#detail-message").html(extraText);
    } else {
        $("#detail-message").text(extraText);
        $("#details-area").hide();
    }

    $(".alert").alert()

    $("#close-alert-btn").click(function() {
        $("#alert-message").text('');
        $(this).parent().hide();
    });
}


/**
 * Handler to allow search of the ontologies table
 */
$(document).ready(function(){
  $("#table-search").val('');
  $("#table-search").on("keyup", function() {
    var value = $(this).val().toLowerCase();
    doTableSearch(value)
  });
});

let hasChanged = false;
/**
 * Handler to show popup when you leave the page, only if the code editor has unsaved changes.
 */
window.addEventListener('beforeunload', (event) => {
  get_commit_btn.disabled=true;
  if (hasChanged) {
    event.returnValue = 'You have unsaved changes. Are you sure you want to leave?';
  }
});


/**
 * Applies a particular search value to filter the ontologies table
 */
function doTableSearch(searchVal) {
    $("#tb-ontologies tr").filter(function() {
      $(this).toggle($(this).text().toLowerCase().indexOf(searchVal) > -1)
    });
    var rowCount = $('#tb-ontologies tr:visible').length;
    $("#search-result-count").text(rowCount+" rows");
}

/**
 * Removes any applied search filters from the ontologies table
 */
function clearTableSearch() {
    $("#table-search").val('');
    doTableSearch('');
}


/**
 * Initialize the editor instance if the element with the id "code" exists.
 */
var editor;
if (document.getElementById("code")) {
  editor = CodeMirror.fromTextArea(document.getElementById("code"), {
    /* Instantiates a CodeMirror editor object from the HTML text area called "code" */
    mode: "text/x-yaml",
    theme: "default",
    lineNumbers: true,
    matchBrackets: true,
    showCursorWhenSelecting: true,
    extraKeys: {
      "F11": function(cm) {
        // If F11 is pressed and we are not already in fullscreen mode, pop up a dialog informing the
        // user how to get out of it:
        if (!cm.getOption("fullScreen")) {
          bootbox.alert({
            title: 'Entering fullscreen editor mode',
            message: 'To leave fullscreen mode, press F11 or Esc',
            closeButton: false,
          });
        }
        // Toggle fullscreen mode:
        cm.setOption("fullScreen", !cm.getOption("fullScreen"));
      },
      "Esc": function(cm) {
        // Pressing escape leaves fullscreen mode if we are currently in it:
        if (cm.getOption("fullScreen"))
          cm.setOption("fullScreen", false);
      },
      Tab: function(cm) {
        // Pressing the tab key actually produces spaces, not tabs:
        var spaces = Array(cm.getOption("indentUnit") + 1).join(" ");
        cm.replaceSelection(spaces);
      },
    }
  });

  /**
   * Add our custom hinting function to the editor
   */
  CodeMirror.commands.autocomplete = function(cm) {
    cm.showHint({hint: purlYamlHint, completeSingle: false});
  }


  /**
   * Activate hint popup on any letter key press
   */
  editor.on("keyup", function (cm, event) {
    // If the autocompletion popup is not already active, and if the user has typed a letter,
    // then activate the autocompletion popup:
    if (!cm.state.completionActive) {
      // Letter keys only:
      keyPressed = event.key.toLowerCase();
      if (keyPressed === ':' || keyPressed === '/' || (keyPressed >= 'a' && keyPressed <= 'z')) {
        CodeMirror.commands.autocomplete(cm);
      }
    }
  });


  /**
   * Disable the pr button when the contents of the editor are changed, and make sure the cursor
   * stays in view. The latter is important because sometimes autocomplete will insert multiple
   * lines into the editor.
   */
  editor.on("changes", function() {
    get_commit_btn().disabled = true;
    hasChanged = true;
    set_draft(false);
    editor.scrollIntoView(what={line: editor.getCursor().line, ch: 0}, margin=12);
  });


  /**
   * Activate context-sensitive help on any navigation
   */
  editor.on("cursorActivity", function (cm, event) {
    contextSensitiveHelp(editor);
  });
}

/**
 *  Display context-sensitive help while navigating the editor
 */
var contextSensitiveHelp = function(editor) {
  var cursor = editor.getCursor();
  var getContext = function() {
    /* Finds the nearest root-level directive above the current line (if one exists) and returns its
       name. */
    var lineNum = cursor.line;
    var matches = /^(\w+):/.exec(editor.getLine(lineNum));
    while (!matches && lineNum > 0) {
      matches = /^(\w+):/.exec(editor.getLine(--lineNum));
    }
    return matches && matches[1];
  };

  var context = getContext();

  //Get the edit JSON schema
  var keyList = Object.keys(editing_schema['properties']);
  var keyListLength = keyList.length;

  //Context-sensitive help based on schema
  for (var i = 0; i < keyListLength; i++) {
    var keyValue = keyList[i];
    if (context === keyValue) {
      $("#help-area").show();
      if (editing_schema['properties'][keyValue]['description'] !== undefined) {
        $("#help-area").html(keyValue + ": "+ editing_schema['properties'][keyValue]['description']);
      } else {
        $("#help-area").html(keyValue);
      }
    }
  }


}

/**
 * Generates completion hints depending on the current cursor position of the yaml file
 */
var purlYamlHint = function(editor, options) {
  var cursor = editor.getCursor();
  var thisLine = editor.getLine(cursor.line);
  var currEnd = cursor.ch;
  var currStart = currEnd;

  // Look left and right from the current cursor position to have in view the entire word at that
  // location:
  while (currStart && /[:\/\w]+/.test(thisLine.charAt(currStart - 1))) {
    --currStart;
  }
  while (currEnd && /[:\/\w]+/.test(thisLine.charAt(currEnd))) {
    ++currEnd;
  }
  var currWord = thisLine.slice(currStart, currEnd);

  var getContext = function() {
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

  // Send back a completion hint list contextualised to the current position as well as to
  // the letters that have been typed so far.
  var prevString = thisLine.slice(0, currStart);
  var context = getContext();

  //Get the edit JSON schema
  var keyList = Object.keys(editing_schema['properties']);
  var keyListLength = keyList.length;

  //Autocomplete suggestions (code completion) based on schema
  var listItems = []; //Start with an empty array
  for (var i = 0; i < keyListLength; i++) {
    var keyValue = keyList[i];
    if (editing_schema['properties'][keyValue]['suggest'] === undefined
           || editing_schema ['properties'][keyValue]['suggest'] === true) {
      //Top-level suggestions
      if (prevString === '') {
           var displayTextStr = keyValue+":";
           var replacementTextStr = keyValue+':';
           //Use the schema annotated suggestion if there is one, else build it
           if (editing_schema['properties'][keyValue]['suggestion'] !== undefined) {
              if ( editing_schema['properties'][keyValue]['type']=='array' ) {
                replacementTextStr += '\n- '+editing_schema['properties'][keyValue]['suggestion'];
              } else if (editing_schema['properties'][keyValue]['type'] == 'object') {
                replacementTextStr += '\n '+editing_schema['properties'][keyValue]['suggestion'];
              } else {
                replacementTextStr += ' '+editing_schema['properties'][keyValue]['suggestion'];
              }
           } else if ( editing_schema['properties'][keyValue]['type']=='array' ) {
               if (editing_schema['properties'][keyValue]['items']['type'] === 'object' &&
                    editing_schema['properties'][keyValue]['items']['properties'] !== undefined ) {
                      replacementTextStr += ' \n- ';
                      var subKeyList = Object.keys(editing_schema['properties'][keyValue]['items']['properties']);
                      var subKeyListLength = subKeyList.length;
                      for (var j=0; j<subKeyListLength; j++) {
                         var subKeyValue = subKeyList[j];
                         replacementTextStr += subKeyValue+': \n  ';
                      }
               } else {
                      replacementTextStr += '\n- ';
               }
           } else if (editing_schema['properties'][keyValue]['type'] === 'object') {
              if (editing_schema['properties'][keyValue]['properties'] !== undefined ) {
                  replacementTextStr += '\n  ';
                  var subKeyList = Object.keys(editing_schema['properties'][keyValue]['properties']);
                  var subKeyListLength = subKeyList.length;
                  for (var j=0; j<subKeyListLength; j++) {
                     var subKeyValue = subKeyList[j];
                     replacementTextStr += subKeyValue+': \n  ';
                  }
              } else {
                  replacementTextStr += ' \n ';
              }
           } else if (editing_schema['properties'][keyValue]['type'] === 'string' &&
              editing_schema['properties'][keyValue]['enum'] !== undefined) {
                var subKeyList = editing_schema['properties'][keyValue]['enum'];
                replacementTextStr += ' '+subKeyList[0];
           } else {
              replacementTextStr += ' ';
           }
        listItems.push({displayText: displayTextStr, text: replacementTextStr});
      } else if (prevString === keyValue+": ") { //Second level enum suggestions
          if (editing_schema['properties'][keyValue]['type'] === 'string') {
              if (editing_schema['properties'][keyValue]['enum'] !== undefined ) {
                  var subKeyList = editing_schema['properties'][keyValue]['enum'];
                  var subKeyListLength = subKeyList.length;
                  for (var j=0; j<subKeyListLength; j++) {
                     var subKeyValue = subKeyList[j];
                     listItems.push({displayText: subKeyValue, text: subKeyValue});
                  }
              }
          }
      } else if ( context === keyValue && ( /^$/.test(prevString) || /^-\s+$/.test(prevString) ||
             /^\s+$/.test(prevString) || /^\s\s+$/.test(prevString) ) ) {   //Second level suggestions for arrays and objects
          if (editing_schema['properties'][keyValue]['type'] === 'object') {
              if (editing_schema['properties'][keyValue]['properties'] !== undefined ) {
                  var subKeyList = Object.keys(editing_schema['properties'][keyValue]['properties']);
                  var subKeyListLength = subKeyList.length;
                  for (var j=0; j<subKeyListLength; j++) {
                     var subKeyValue = subKeyList[j];
                     listItems.push({displayText: subKeyValue+":", text: subKeyValue+": "});
                  }
              }
          } else if (editing_schema['properties'][keyValue]['type'] === 'array') {
              if (editing_schema['properties'][keyValue]['items']['properties'] !== undefined ) {
                  var subKeyList = Object.keys(editing_schema['properties'][keyValue]['items']['properties']);
                  var subKeyListLength = subKeyList.length;
                  for (var j=0; j<subKeyListLength; j++) {
                     var subKeyValue = subKeyList[j];
                     if (editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['type'] === 'string'
                      && editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['enum'] !== undefined ) {
                        var subSubKeyList = editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['enum'];
                        listItems.push({displayText: subKeyValue+":", text: subKeyValue+": "+subSubKeyList[0]});
                     } else if (editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['type'] === 'array'
                      && editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['items']['properties'] !== undefined ) {
                        var subSubKeyList = Object.keys(editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['items']['properties']);
                        var subSubKeyListLength = subSubKeyList.length;
                        var replacementTextStr = subKeyValue+": \n";
                        for (var k=0; k<subSubKeyListLength; k++) {
                            var subSubKeyValue = subSubKeyList[k];
                            replacementTextStr += '  '+subSubKeyValue+": \n";
                        }
                        listItems.push({displayText: subKeyValue+":", text: replacementTextStr});
                     } else {
                        listItems.push({displayText: subKeyValue+":", text: subKeyValue+": "});
                     }
                  }
              }
          } else if (editing_schema['properties'][keyValue]['suggestion'] !== undefined ){
              suggestion = editing_schema['properties'][keyValue]['suggestion'];
              suggRegex = new RegExp("^"+suggestion);
              if (! suggRegex.test(currWord)) {
                  listItems.push({displayText: suggestion, text: suggestion});
              }
          }
      }
      //Third level suggestions for objects nested within arrays
      if (  editing_schema['properties'][keyValue]['type']=='array' &&
          editing_schema['properties'][keyValue]['items']['type'] === 'object' &&
          editing_schema['properties'][keyValue]['items']['properties'] !== undefined ) {
              var subKeyList = Object.keys(editing_schema['properties'][keyValue]['items']['properties']);
              var subKeyListLength = subKeyList.length;
              for (var j=0; j<subKeyListLength; j++) {
                 var subKeyValue = subKeyList[j];
                 var subKeyRegex = new RegExp('^\\s+'+subKeyValue+':\\s+$');
                 if (editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['type'] === 'array'
                    && editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['items']['properties'] !== undefined) {
                    if (subKeyRegex.test(prevString) && context === keyValue) {
                        var subSubKeyList = Object.keys(editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['items']['properties']);
                        var subSubKeyListLength = subSubKeyList.length;
                        for (var k=0; k<subSubKeyListLength; k++) {
                            var subSubKeyValue = subSubKeyList[k];
                            listItems.push({displayText: subSubKeyValue+":", text: subSubKeyValue+": "});
                        }
                    }
                 } else if ( editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['type'] === 'string'
                        && 'enum' in editing_schema['properties'][keyValue]['items']['properties'][subKeyValue] ) {
                    if (subKeyRegex.test(prevString) && context === keyValue) {
                        var subSubKeyList = editing_schema['properties'][keyValue]['items']['properties'][subKeyValue]['enum'];
                        var subSubKeyListLength = subSubKeyList.length;
                        for (var k=0; k<subSubKeyListLength; k++) {
                            var subSubKeyValue = subSubKeyList[k];
                            listItems.push({displayText: subSubKeyValue, text: subSubKeyValue});
                        }
                    }
                 }
              }
          }
      //end of third level suggestions
    }
  }

  return {list: pruneReplacementList(listItems),
            from: from, to: to};

};

/**
 * Validates the contents of the editor, displaying the validation result in the status area.
 */
var validate = function(filename, editor_type) {
  // Save the contents of the editor to its associated text area:
  editor.save();

  // Extract the code from the text area:
  var code = document.getElementById("code").value;

  // Clear the status area:
  showAlertFor("Validating ...", "alert-info") ;

  // Before doing anything else, make sure that the idspace indicated in the code matches the
  // idspace being edited:
  if (editor_type == 'registry') {
     var idspace_name = 'id';
     var expected_idspace = filename.substring(0, filename.lastIndexOf('.'));
     var actual_idspace = code.match(/[^\S\r\n]*id:[^\S\r\n]+(.+?)[^\S\r\n]*\n/m);
  }
  if (editor_type == 'purl') {
     var idspace_name = 'idspace';
     var expected_idspace = filename.substring(0, filename.lastIndexOf('.')).toUpperCase();
     var actual_idspace = code.match(/[^\S\r\n]*idspace:[^\S\r\n]+(.+?)[^\S\r\n]*\n/m);
  }
  if (!actual_idspace) {
    showAlertFor("Validation failed: \'" + idspace_name + ": \' is required", "alert-danger") ;
    get_commit_btn().disabled = true; //Don't enable "submit as draft" option for ID validation failure
    return;
  }
  else if (actual_idspace[1] !== expected_idspace) {
    showAlertFor("Validation failed: \'" + idspace_name + ": " + actual_idspace[1] +
      "\' does not match the expected value: \'" + expected_idspace + "\'", "alert-danger")  ;
    get_commit_btn().disabled = true; //Don't enable "submit as draft" option for ID validation failure
    return;
  }

  // Embed the code into a POST request and send it to the server for processing.
  // If the validation is successful, enable the Pr button, otherwise disable it.
  var request = new XMLHttpRequest();
  request.onreadystatechange = function() {
    $("*").css("cursor", "default");
    if (request.readyState === 4) {
      if (!request.status) {
        showAlertFor("Problem communicating with server","alert-danger");
        get_commit_btn().disabled = true;
      } else {
         alertTextDetail = '';
         try { //Parse JSON if possible, use "result type" to decide message
            var response = JSON.parse(request.responseText);
            if (response.result_type === 'error') {
                alertText = 'Validation failed ';
                alertLevel = "alert-danger";
                get_commit_btn().disabled = false;
                set_draft(true);
            } else if (response.result_type === 'warning') {
                alertText = 'Warning ';
                alertLevel = "alert-warning";
                get_commit_btn().disabled = false;
                set_draft(false);
            } else if (response.result_type === 'info') {
                alertText = 'Information ';
                alertLevel = "alert-info";
                get_commit_btn().disabled = false;
                set_draft(false);
            } else {
                alertText='Unknown response type: ' + response.result_type;
                alertLevel="alert-danger";
                get_commit_btn().disabled = true;
                set_draft(false);
            }
            // If the line number is valid, then add it to the message
            if (response.line_number) {
                alertText += response.line_number >= 0 ? ('. At line ' + response.line_number + ': ') : ': ';
            }
            // and highlight that line in the editor while scrolling it into view.
            if (response.line_number >= 0) {
                var marker = editor.markText({line: response.line_number - 1, ch: 0},
                                       {line: response.line_number, ch: 0},
                                       {className: "line-error", clearOnEnter: true});

                editor.scrollIntoView(what={line: response.line_number, ch: 0}, margin=32);

                // Clear the highlighting after 5000ms:
                setTimeout(function() {
                    marker.clear();
                }, 5000);
            }
            //Show additional error details in the message
            if (response.details) {
                alertText += response.summary + '\n';
                alertTextDetail = response.details + '\n';
            }
        } catch (err) {
            // No JSON information, just use the HTTP status to decide what to do
            if (request.status === 200) {
                alertText = "Validation successful";
                alertLevel = "alert-success";
                get_commit_btn().disabled = false;
                set_draft(false);
            } else if (request.status === 400) {
                alertText = 'Validation failed';
                alertLevel = "alert-danger";
                get_commit_btn().disabled = false;
                set_draft(true);  //Enable "submit as draft" option
            }
        }
        showAlertFor(alertText,alertLevel,alertTextDetail);
      }
    }
  }
  request.open('POST', '/validate', true);
  request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
  request.send("code=" + encodeURIComponent(code) +
               "&editor_type=" + editor_type);
  $("*").css("cursor", "progress");
};


/**
 * Submit a pull request to github to add a new configuration to the repository.
 */
var add_config = function(filename, editor_type, issueNumber, addIssueLink) {
  var projectName = filename.toUpperCase().substring(0, filename.lastIndexOf('.'));
  $("#commit-msg").attr('value','Adding ' + filename);
  if (editor_type == 'registry') {
    $("#descr").attr('value','Adding registry configuration for '+projectName +
                     '. Closes #' + issueNumber);
  }
  else if (editor_type == 'purl') {
    $("#descr").attr('value','Adding PURL configuration for '+ projectName +
             (addIssueLink !== 'None'?'. See also '+addIssueLink : '') );
  }
  // Get a confirmation from the user:
  var modal = bootbox.dialog({
      message: $("#message-box").html(),
      title: "Please describe the new configuration you would like to add: " +
      projectName,
        buttons: {
          confirm: {
            label: 'Submit',
            className: 'btn-danger',
            callback: function() {
                var aForm = modal.find(".form");
                var formData = aForm.serializeArray(),
                    dataObj = {};
                $(formData).each(function(i, field){
                  dataObj[field.name] = field.value;
                });
                var msgTitle = dataObj["commit-msg"];
                var msgBody = dataObj["descr"];
              if (msgTitle !== null && msgTitle !== undefined) {
                if (!msgTitle || msgTitle.trim() === "") {
                  bootbox.alert({
                    closeButton: false,
                    message: "Commit message cannot be empty. New configuration was not submitted."});
                  return;
                }

                // Disable the add button:
                get_commit_btn().disabled = true;

                // Extract the code from the text area:
                var code = document.getElementById("code").value;

                showAlertFor("Submitting new configuration ...","alert-info");

                // Embed the code into a request.
                var request = new XMLHttpRequest();
                // Define a function to handle a state change of the request:
                request.onreadystatechange = function() {
                  $("*").css("cursor", "default");
                  if (request.readyState === 4) {
                    if (!request.status) {
                      showAlertFor("Problem communicating with server","alert-danger");
                    }
                    else if (request.status === 200) {
                      var response = JSON.parse(request.responseText);
                      var prInfo = response['pr_info'];
                      var nextBtn = document.getElementById('next-step-btn');
                      if (nextBtn) {
                          nextBtn.disabled = false;
                          if (editor_type == 'registry') {
                            nextBtn.addEventListener("click", function() {
                               loadEditorFor(issueNumber,prInfo['html_url']);
                            });
                          } else {
                            nextBtn.addEventListener("click", function() {
                               window.location.href = "/";
                             });
                          }
                      }
                      var nextStepTxt = '' ;
                      if (editor_type == 'registry' && issueNumber) {
                        nextStepTxt = 'The next step is to ' +
                      '<a href="javascript:loadEditorFor(\'' + issueNumber + '\',\'' +
                        prInfo['html_url'] +'\');">Create a PURL config</a>.';
                      }
                      if (editor_type == 'purl' && addIssueLink) {
                        nextStepTxt = 'You\'re all done! The PR for the registry config was <a href="'+
                         addIssueLink+'" target="__blank">also</a> successfully submitted.';
                      }
                      showAlertFor('New configuration submitted successfully. It will be ' +
                        'reviewed by a moderator before being added to the repository. Click ' +
                        '<a href="' + prInfo['html_url'] + '" target="__blank">here</a> to view your ' +
                        'pull request on GitHub. ' + nextStepTxt,"alert-success");
                      hasChanged = false;
                    }
                    else {
                      // Display the error message in the status area. Note that we must replace any angle
                      // angle brackets with HTML escape codes.
                      alertText = "Submission of new configuration failed.\n\n" +
                        request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                      showAlertFor(alertText,"alert-danger");
                    }
                  }
                }
                // Post the request to the server.
                request.open('POST', '/add_config', true);
                request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
                request.send('filename=' + filename +
                             '&commit_msg=' + msgTitle +
                             '&draft=' + draft +
                             '&code=' + encodeURIComponent(code) +
                             '&editor_type=' + editor_type +
                             '&long_msg='+ msgBody )
                $("*").css("cursor", "progress");
              }
            }
          },
          cancel: {
            label: 'Cancel',
            className: 'btn-primary',
            callback: function() {
            }
          }
        }
  });
}

/**
 * Submit a pull request to github to update the given configuration file in the repository.
 */
var update_config = function(filename,editor_type) {
  var projectName = filename.toUpperCase().substring(0, filename.lastIndexOf('.'));
  $("#commit-msg").attr('value','Updating ' + filename);
  if (editor_type == 'registry') {
    $("#descr").attr('value','Updating registry configuration for '+projectName);
  }
  else if (editor_type == 'purl') {
    $("#descr").attr('value','Updating PURL configuration for '+ projectName);
  }

  // Get a confirmation from the user:
  var modal = bootbox.dialog({
    title: "You are about to submit changes. Please describe the changes you have made to " +
      filename.toUpperCase().substring(0, filename.lastIndexOf('.')),
    message: $("#message-box").html(),
    buttons: {
      confirm: {
        label: 'Submit',
        className: 'btn-danger',
        callback: function() {
            var aForm = modal.find(".form");
            var formData = aForm.serializeArray(),
                dataObj = {};
            $(formData).each(function(i, field){
              dataObj[field.name] = field.value;
            });
            var commit_msg = dataObj["commit-msg"];
            var msgBody = dataObj["descr"];
            if (commit_msg !== null && commit_msg !== undefined) {
                if (!commit_msg || commit_msg.trim() === "") {
                  bootbox.alert({
                    closeButton: false,
                    message: "Commit message cannot be empty. Your change has not been submitted."});
                  return;
                }

                // Disable the update button:
                get_commit_btn().disabled = true;

                // Extract the code from the text area:
                var code = document.getElementById("code").value;

                showAlertFor("Submitting update ...","alert-info");

                // Embed the code into a request.
                var request = new XMLHttpRequest();
                // Define a function to handle a state change of the request:
                request.onreadystatechange = function() {
                  $("*").css("cursor", "default");
                  if (request.readyState === 4) {
                    if (!request.status) {
                      showAlertFor("Problem communicating with server","alert-danger");
                    }
                    else if (request.status === 200) {
                      var response = JSON.parse(request.responseText);
                      var prInfo = response['pr_info'];
                      showAlertFor('Update submitted successfully. The changes will be ' +
                        'reviewed by a moderator before being added to the repository. Click ' +
                        '<a href="' + prInfo['html_url'] + '" target="__blank">here</a> to view your ' +
                        'pull request on GitHub.',"alert-success");
                      hasChanged = false;
                    }
                    else {
                      // Display the error message in the status area. Note that we must replace any angle
                      // angle brackets with HTML escape codes.
                      alertText = "Submission of update failed.\n\n" +
                        request.responseText.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                      showAlertFor(alertText,"alert-danger");
                    }
                  }
                }
                // Post the request to the server.
                request.open('POST', '/update_config', true);
                request.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
                request.send('filename=' + filename +
                             '&commit_msg=' + commit_msg +
                             '&draft='+ draft +
                             '&code=' + encodeURIComponent(code) +
                             '&editor_type='+editor_type +
                             '&long_msg=' + msgBody)
                $("*").css("cursor", "progress");
          }
        }
      },
      cancel: {
        label: 'Cancel',
        className: 'btn-primary'
      }
    }
  });
};

/**
 * Send a non-AJAX POST request to redirect to a new editor corresponding to the PURL editor.
 */
var loadEditorFor = function(issueNo, addL) {
    var form = document.createElement('form');
    document.body.appendChild(form);
    form.method = 'post';
    form.action = '/edit_new';

    var issueNumberI = document.createElement('input');
    issueNumberI.type = 'hidden';
    issueNumberI.name = 'issueNumber';
    issueNumberI.value = issueNo;
    form.appendChild(issueNumberI);

    var editorTypeI = document.createElement('input');
    editorTypeI.type = 'hidden';
    editorTypeI.name = 'editor_type';
    editorTypeI.value = 'purl';
    form.appendChild(editorTypeI);

    var addLI = document.createElement('input');
    addLI.type = 'hidden';
    addLI.name = 'addIssueLink'
    addLI.value = addL;
    form.appendChild(addLI);

    form.submit();
}



