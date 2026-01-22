const vscode = require('vscode');
const fetch = require('node-fetch');

function activate(context) {

    console.log("CodeGuardian extension activated.");

    let disposable = vscode.commands.registerCommand('codeguardian.scanCode', async function () {
        const editor = vscode.window.activeTextEditor;

        if (!editor) {
            vscode.window.showErrorMessage("No active editor open.");
            return;
        }

        const code = editor.document.getText();
        vscode.window.showInformationMessage("Scanning code with CodeGuardian...");

        try {
            const response = await fetch("http://127.0.0.1:8000/scan", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ code }),
            });

            const result = await response.json();
            const output = vscode.window.createOutputChannel("CodeGuardian Findings");

            output.clear();
            output.appendLine("=== CodeGuardian Scan Results ===\n");
            output.appendLine(result.message + "\n");

            result.findings.forEach((f, i) => {
                output.appendLine(`Issue ${i + 1}`);
                output.appendLine(`Severity: ${f.severity}`);
                output.appendLine(`Policy: ${f.policy}`);
                output.appendLine(`Line: ${f.line}`);
                output.appendLine(`Message: ${f.message}`);
                output.appendLine(`Suggested Fix: ${f.suggested_fix}`);
                output.appendLine("-------------------------------\n");
            });

            output.show(true);
        } catch (err) {
            vscode.window.showErrorMessage("Error contacting backend: " + err);
        }
    });

    context.subscriptions.push(disposable);
}

function deactivate() {}

module.exports = { activate, deactivate };
