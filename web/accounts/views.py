from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from .models import User
from django import forms

def register(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        if User.objects.filter(email=email).exists():
            messages.error(request, 'Email already registered.')
            return redirect('accounts:register')
        user = User.objects.create_user(email=email, password=password)
        login(request, user)
        return redirect('decks:list')
    return render(request, 'accounts/register.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = authenticate(request, email=email, password=password)
        if user is not None:
            login(request, user)
            return redirect('decks:list')
        else:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'accounts/login.html')

def logout_view(request):
    logout(request)
    return redirect('accounts:login')
