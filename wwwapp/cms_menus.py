from django.urls import reverse
from django.utils.safestring import mark_safe
from menus.base import Menu, NavigationNode, Modifier
from menus.menu_pool import menu_pool

from wwwapp.models import Camp, ResourceYearPermission, UserProfile


class WWWProgramMenu(Menu):
    def get_nodes(self, request):
        current_year = Camp.current()
        return [
            NavigationNode(
                title='Program',
                url=reverse('program', args=[current_year.pk]),
                id='wwwapp_program',
            ),
        ]


class WWWInternetyMenu(Menu):
    def get_nodes(self, request):
        visible_resources = []
        if request.user.is_authenticated:
            resources = ResourceYearPermission.objects.exclude(access_url__exact="")
            if request.user.has_perm('wwwapp.access_all_resources'):
                visible_resources = resources.all()
            else:
                try:
                    user_profile = UserProfile.objects.get(user=request.user)
                    visible_resources = resources.filter(year__in=user_profile.all_participation_years())
                except UserProfile.DoesNotExist:
                    pass

        if not visible_resources:
            return []

        nodes = [
            NavigationNode(
                title='Internety',
                url=None,
                id='internety',
            ),
        ]
        for resource in visible_resources:
            nodes.append(
                NavigationNode(
                    title=resource.display_name,
                    url=resource.access_url,
                    id='internety_{}'.format(resource.pk),
                    parent_id='internety',
                )
            )
        return nodes


class WWWAdminMenu(Menu):
    def get_nodes(self, request):
        current_year = Camp.current()
        if (not request.user.is_staff and
            not request.user.has_perm('wwwapp.see_all_users') and
            not request.user.has_perm('wwwapp.see_all_workshops') and
            not request.user.has_perm('wwwforms.see_form_results') and
            not request.user.has_perm('wwwapp.export_workshop_registration')):
            return []
        nodes = [
            NavigationNode(
                title='Admin',
                url=None,
                id='wwwapp_admin',
            ),
        ]
        if request.user.has_perm('perms.wwwapp.see_all_users'):
            nodes.extend([
                NavigationNode(
                    title='Uczestnicy',
                    url=reverse('participants', args=[current_year.pk]),
                    id='participants',
                    parent_id='wwwapp_admin',
                ),
                NavigationNode(
                    title='Prowadzący',
                    url=reverse('lecturers', args=[current_year.pk]),
                    id='lecturers',
                    parent_id='wwwapp_admin',
                ),
            ])
        if request.user.has_perm('perms.wwwapp.see_all_workshops'):
            nodes.extend([
                NavigationNode(
                    title='Warsztaty',
                    url=reverse('workshops', args=[current_year.pk]),
                    id='workshops',
                    parent_id='wwwapp_admin',
                ),
            ])
        if request.user.has_perm('perms.wwwapp.see_form_results'):
            nodes.extend([
                NavigationNode(
                    title='Formularze',
                    url=reverse('form_list'),
                    id='forms',
                    parent_id='wwwapp_admin',
                ),
            ])
        if request.user.has_perm('perms.wwwapp.see_all_users'):
            nodes.extend([
                NavigationNode(
                    title='Wszyscy ludzie',
                    url=reverse('all_people'),
                    id='all_people',
                    parent_id='wwwapp_admin',
                ),
                NavigationNode(
                    title='Adresy email',
                    url=reverse('emails', args=[current_year.pk]),
                    id='emails',
                    parent_id='wwwapp_admin',
                ),
            ])
        return nodes


class WWWQualificationMenu(Menu):
    def get_nodes(self, request):
        return [
            NavigationNode(
                title='Kwalifikacja',
                url=reverse('mydata_status'),
                id='wwwapp_qualification',
            ),
        ]


class WWWArticlesMenu(Menu):
    def get_nodes(self, request):
        return [
            NavigationNode(
                title='Artykuły',
                url=None,
                id='wwwapp_articles',
            ),
        ]


class WWWArticlesModifier(Modifier):
    def modify(self, request, nodes, namespace, root_id, post_cut, breadcrumb):
        articles = next(filter(lambda x: x.id == 'wwwapp_articles', nodes), None)
        if not articles:
            return nodes

        for node in nodes:
            if not node.parent and node.attr.get('is_page', False) and not node.attr.get('is_home', False):
                node.parent = articles
                node.parent_id = articles.id
                articles.children.append(node)
            if node.attr.get('is_home', False):
                node.title = mark_safe('<span class="d-none d-lg-block"><i class="fas fa-home"></i></span><span class="d-block d-lg-none">Strona główna</span>')

        if len(articles.children) == 0:
            nodes.remove(articles)
        return nodes


menu_pool.register_menu(WWWProgramMenu)
menu_pool.register_menu(WWWInternetyMenu)
menu_pool.register_menu(WWWAdminMenu)
menu_pool.register_menu(WWWArticlesMenu)
menu_pool.register_menu(WWWQualificationMenu)
menu_pool.register_modifier(WWWArticlesModifier)
