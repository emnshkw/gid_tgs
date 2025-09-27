from rest_framework.views import APIView
from rest_framework.response import Response
from .serializers import YaAccountSelizalier
from datetime import datetime, timedelta
from .models import YaAccountModel
class YaAccountAPIView(APIView):
    def get(self, request, *args, **kwargs):
        need_update_accounts = YaAccountModel.objects.filter(need_update=True)
        return Response({'status':'success','data':YaAccountSelizalier(need_update_accounts,many=True).data})
    def post(self,request,*args,**kwargs):
        data = request.data
        name = data.get('name')
        city = data.get('city')
        categories = data.get('categories')
        new_cats = data.get('new_cats')
        del_cats = data.get('del_cats')
        new_city = data.get('new_city')
        need_update = data.get('need_update')
        new = YaAccountModel.objects.create(name=name,city=city,categories='\n'.join(categories),new_cats=new_cats,new_city=new_city,del_cats=del_cats,need_update=need_update)
        return Response({'status':'success','data':YaAccountSelizalier(new).data})
    def patch(self,request,*args,**kwargs):
        data = request.data
        account_name = data.get('name')
        account = YaAccountModel.objects.get(name=account_name)
        added_cats = data.get('added_cats')
        if added_cats is not None:
            cur_cats = [i.replace('\r','').replace('\n','') for i in account.categories.split('\n')]
            new_cats = [i.replace('\r','').replace('\n','') for i in account.new_cats.split('\n')]
            for added_cat in added_cats:
                if added_cat not in cur_cats:
                    cur_cats.append(added_cat)
                    new_cats.remove(added_cat)
            account.categories = '\n'.join(cur_cats)
            account.new_cats = '\n'.join(new_cats)
        deleted_cats = data.get('deleted_cats')
        if deleted_cats is not None:
            cur_cats = [i.replace('\r', '').replace('\n', '') for i in account.categories.split('\n')]
            del_cats = [i.replace('\r', '').replace('\n', '') for i in account.del_cats.split('\n')]
            for deleted_cat in deleted_cats:
                cur_cats = cur_cats.remove(deleted_cat)
                del_cats = del_cats.remove(deleted_cat)
            account.categories = '\n'.join(cur_cats)
            account.del_cats = '\n'.join(del_cats)
        new_city = data.get('new_city')
        if new_city is not None:
            account.city = new_city
        if account.new_cats == '' and account.del_cats == '' and account.new_city == '':
            account.need_update = False
        account.save()
        return Response({"status":'success','message':"Изменения внесены!"})