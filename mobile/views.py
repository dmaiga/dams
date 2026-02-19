from django.shortcuts import render, redirect
from django.contrib.auth import login
from core.forms import TelephoneOrUsernameLoginForm


def mobile_login(request):

    if request.user.is_authenticated:
        return redirect("mobile_home")

    form = TelephoneOrUsernameLoginForm(request, data=request.POST or None)

    if request.method == "POST":
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("mobile_home")

    return render(request, "mobile/login.html", {"form": form})


from django.contrib.auth.decorators import login_required

@login_required
def mobile_home(request):

    agent = request.user.agent

    if agent.est_rot:
        return redirect("dashboard_rot")

    if agent.est_superviseur:
        return redirect("tableau_de_bord_superviseur")

    return redirect("dashboard_agent")
