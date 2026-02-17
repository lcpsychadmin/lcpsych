from django import forms
from .models import JoinOurTeamSubmission


class JoinOurTeamForm(forms.ModelForm):
    max_resume_size_mb = 15

    class Meta:
        model = JoinOurTeamSubmission
        fields = [
            "first_name",
            "last_name",
            "email",
            "message",
            "resume",
        ]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def clean_resume(self):
        file = self.cleaned_data.get("resume")
        if not file:
            return file
        max_bytes = self.max_resume_size_mb * 1024 * 1024
        if file.size > max_bytes:
            raise forms.ValidationError(
                f"Resume is too large. Please upload a file under {self.max_resume_size_mb} MB."
            )
        allowed_exts = {"pdf", "doc", "docx"}
        ext = (file.name.rsplit(".", 1)[-1] or "").lower()
        if ext not in allowed_exts:
            raise forms.ValidationError("Please upload a PDF or Word document (pdf, doc, docx).")
        return file
